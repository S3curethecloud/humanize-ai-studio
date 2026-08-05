from __future__ import annotations

import json
from time import perf_counter
from typing import Any

import httpx

from app.domain.models import RewriteChange, RewriteRequest
from app.providers.base import ProviderUsage, RewriteProviderResult
from app.providers.claim_integrity import find_claim_integrity_violations
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.providers.rewrite_distance import evaluate_rewrite_distance

REWRITE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "type": "object",
        "properties": {
            "rewritten_text": {
                "type": "string",
            },
        },
        "required": ["rewritten_text"],
        "additionalProperties": False,
    },
}


class CloudflareWorkersAIProvider:
    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        model_name: str = "@cf/openai/gpt-oss-20b",
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not account_id.strip():
            raise RewriteProviderConfigurationError("Cloudflare account ID must not be empty.")

        if not api_token.strip():
            raise RewriteProviderConfigurationError("Cloudflare API token must not be empty.")

        if not model_name.strip():
            raise RewriteProviderConfigurationError("Cloudflare model name must not be empty.")

        self._account_id = account_id.strip()
        self._api_token = api_token.strip()
        self._model_name = model_name.strip()
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def provider_name(self) -> str:
        return "cloudflare-workers-ai"

    def _post_payload(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        try:
            if self._client is not None:
                return self._client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )

            with httpx.Client() as client:
                return client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
        except httpx.HTTPError as exc:
            raise RewriteProviderTransportError("Cloudflare Workers AI request failed.") from exc

    def rewrite(self, request: RewriteRequest) -> RewriteProviderResult:
        started_at = perf_counter()

        endpoint = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self._account_id}/ai/run/{self._model_name}"
        )

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": self._user_prompt(request),
                },
            ],
            "response_format": REWRITE_RESPONSE_SCHEMA,
            "temperature": 0.4,
            "max_tokens": 4096,
        }

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        response = self._post_payload(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
        )

        if response.is_error:
            raise RewriteProviderResponseError(
                "Cloudflare Workers AI returned "
                f"HTTP {response.status_code}: "
                f"{_safe_error_detail(response)}"
            )

        response_body = _parse_json_object(response)

        if response_body.get("success") is not True:
            errors = response_body.get("errors", [])
            raise RewriteProviderResponseError(
                f"Cloudflare Workers AI reported failure: {errors!r}"
            )

        generated_output = _extract_generated_output(response_body)
        rewritten_text = _parse_rewritten_text(generated_output)
        usage = _extract_usage(response_body)
        repair_used = False

        integrity_violations = find_claim_integrity_violations(
            source_text=request.text,
            rewritten_text=rewritten_text,
        )

        if integrity_violations:
            violation_summary = "\n".join(
                (f"- {violation.rule_id}: {violation.phrase!r} — {violation.description}")
                for violation in integrity_violations
            )

            required_phrases = tuple(
                dict.fromkeys(
                    violation.phrase
                    for violation in integrity_violations
                    if violation.rule_id == "qualification_removed"
                )
            )

            repair_payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": self._system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": self._repair_prompt(
                            request=request,
                            rejected_text=rewritten_text,
                            violation_summary=violation_summary,
                            required_phrases=required_phrases,
                        ),
                    },
                ],
                "response_format": REWRITE_RESPONSE_SCHEMA,
                "temperature": 0.0,
                "max_tokens": 4096,
            }

            repair_response = self._post_payload(
                endpoint=endpoint,
                headers=headers,
                payload=repair_payload,
            )

            if repair_response.is_error:
                raise RewriteProviderResponseError(
                    "Cloudflare Workers AI repair returned "
                    f"HTTP {repair_response.status_code}: "
                    f"{_safe_error_detail(repair_response)}"
                )

            repair_body = _parse_json_object(repair_response)

            if repair_body.get("success") is not True:
                errors = repair_body.get("errors", [])

                raise RewriteProviderResponseError(
                    f"Cloudflare Workers AI repair reported failure: {errors!r}"
                )

            repair_output = _extract_generated_output(repair_body)
            repaired_text = _parse_rewritten_text(repair_output)
            repair_usage = _extract_usage(repair_body)

            repaired_violations = find_claim_integrity_violations(
                source_text=request.text,
                rewritten_text=repaired_text,
            )

            if repaired_violations:
                repaired_summary = "; ".join(
                    (f"{violation.rule_id}: {violation.phrase!r}")
                    for violation in repaired_violations
                )

                raise RewriteProviderResponseError(
                    f"Cloudflare repair failed claim-integrity validation: {repaired_summary}"
                )

            repair_distance = evaluate_rewrite_distance(
                source_text=request.text,
                rewritten_text=repaired_text,
                intensity=request.intensity,
            )

            if not repair_distance.acceptable:
                raise RewriteProviderResponseError(
                    "Cloudflare repair failed useful-distance "
                    "validation: "
                    f"{repair_distance.reason} "
                    "similarity_ratio="
                    f"{repair_distance.similarity_ratio:.4f}; "
                    "changed_token_count="
                    f"{repair_distance.changed_token_count}; "
                    "moved_token_count="
                    f"{repair_distance.moved_token_count}; "
                    "source_sentence_count="
                    f"{repair_distance.source_sentence_count}; "
                    "rewritten_sentence_count="
                    f"{repair_distance.rewritten_sentence_count}"
                )

            rewritten_text = repaired_text
            usage = _merge_usage(
                usage,
                repair_usage,
            )
            repair_used = True

        changes: list[RewriteChange] = []

        if rewritten_text != request.text:
            changes.append(
                RewriteChange(
                    change_id="change-cloudflare-1",
                    original=request.text,
                    replacement=rewritten_text,
                    reason=(
                        "Cloudflare Workers AI reconstructed the draft using "
                        "the requested audience, tone, and rewrite intensity"
                        + (", followed by one policy-constrained repair." if repair_used else ".")
                    ),
                    change_type="model_reconstruction",
                )
            )

        return RewriteProviderResult(
            text=rewritten_text,
            changes=changes,
            provider_name=self.provider_name,
            model_name=self._model_name,
            prompt_version="cloudflare-humanize-v6",
            latency_ms=round((perf_counter() - started_at) * 1000, 3),
            primary_provider_name=self.provider_name,
            fallback_used=False,
            provider_error_category=None,
            usage=usage,
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a controlled, claim-preserving editorial reconstruction "
            "engine. Rewrite the source so it sounds natural, direct, specific, "
            "and appropriate for the stated audience. Preserve the speaker's "
            "meaning, voice, level of certainty, level of experience, ownership, "
            "scope, and authority. Preserve every name, number, date, metric, "
            "citation, technical term, qualification, limitation, comparison, "
            "and negation exactly unless the request explicitly authorizes a "
            "change. "
            "\n\n"
            "CLAIM-INTEGRITY RULES:\n"
            "- Never strengthen a qualification or level of experience.\n"
            "- Never convert experience into expertise or mastery.\n"
            "- Never convert participation into ownership or leadership.\n"
            "- Never convert contribution into delivery, authorship, or sole "
            "responsibility.\n"
            "- Never add seniority, scale, complexity, business impact, customer "
            "impact, reliability, performance, security, or production claims.\n"
            "- Never add an achievement, result, outcome, metric, capability, "
            "credential, or responsibility that is absent from the source.\n"
            "- Never weaken uncertainty, conditions, limitations, or negations.\n"
            "- Do not infer that a technology list proves expertise in every "
            "listed technology.\n"
            "\n"
            "PROHIBITED INFLATION EXAMPLES:\n"
            "- 'experience' must not become 'extensive experience', 'deep "
            "experience', or 'expertise'.\n"
            "- 'worked with' must not become 'led', 'owned', 'architected', or "
            "'mastered'.\n"
            "- 'helped build' must not become 'built', 'delivered', or 'drove'.\n"
            "- 'contributed to' must not become 'created', 'owned', or "
            "'implemented end to end'.\n"
            "- 'used' must not become 'specialized in', 'expert in', or "
            "'mastered'.\n"
            "\n"
            "STYLE RULES:\n"
            "- Prefer direct subject-verb sentences.\n"
            "- Preserve first-person voice when the source uses first person.\n"
            "- Remove robotic symmetry, repetitive transitions, empty "
            "intensifiers, and formulaic AI phrasing.\n"
            "- Do not replace precise language with promotional résumé language.\n"
            "- Do not add generic endings or vague business-value statements.\n"
            "- Avoid phrases such as 'leveraging a range of technologies', "
            "'across various areas', 'to drive effective solutions', 'proven "
            "track record', 'rapidly evolving landscape', 'robust and seamless', "
            "and 'developed expertise' unless those exact claims appear in the "
            "source.\n"
            "- Do not add an introduction, conclusion, heading, commentary, or "
            "explanation.\n"
            "\n"
            "REWRITE-DISTANCE RULES:\n"
            "- light_polish: correct grammar, punctuation, clarity, and minor "
            "wording only. Preserve sentence structure whenever practical.\n"
            "- moderate_rewrite: restructure sentences and improve flow while "
            "preserving every claim, qualification, scope boundary, and level of "
            "certainty.\n"
            "- deep_reconstruction: substantially reorganize the writing, but do "
            "not strengthen, weaken, broaden, or invent any claim. Deep "
            "reconstruction authorizes structural change, not factual or "
            "professional inflation.\n"
            "\n"
            "Before returning the answer, compare the rewrite against the source "
            "and remove any word or phrase that increases seniority, expertise, "
            "ownership, scope, certainty, or impact. Return only the structured "
            "response required by the schema."
        )

    @staticmethod
    def _repair_prompt(
        *,
        request: RewriteRequest,
        rejected_text: str,
        violation_summary: str,
        required_phrases: tuple[str, ...],
    ) -> str:
        required_phrase_block = (
            "\n".join(f"- {phrase}" for phrase in required_phrases)
            if required_phrases
            else "- None"
        )

        return (
            "The previous rewrite was rejected by deterministic "
            "claim-integrity validation. Regenerate the rewrite exactly once. "
            "Correct every listed violation while preserving all valid "
            "structural and stylistic improvements.\n\n"
            "REJECTED VIOLATIONS:\n"
            f"{violation_summary}\n\n"
            "REQUIRED VERBATIM PHRASES:\n"
            f"{required_phrase_block}\n\n"
            "MANDATORY REPAIR RULES:\n"
            "- Every phrase listed under REQUIRED VERBATIM PHRASES must appear "
            "exactly, with the same words and hyphenation, in the rewrite.\n"
            "- Preserve every protected qualification explicitly.\n"
            "- Restore any qualification or participation boundary removed "
            "from the source.\n"
            "- Remove every unsupported expertise, ownership, seniority, "
            "scope, certainty, and impact claim.\n"
            "- Remove promotional filler and invented outcomes.\n"
            "- Do not copy the rejected wording when it caused a violation.\n"
            "- Do not return the source text verbatim unless the requested "
            "intensity is light_polish and no safe wording improvement exists.\n"
            "- For moderate_rewrite or deep_reconstruction, make at least one "
            "clear structural or lexical improvement while preserving every "
            "claim and required phrase.\n"
            "- For deep_reconstruction, materially reorganize sentence "
            "structure or information order. Move a clause, reorder major "
            "ideas, split a sentence, or combine sentences while preserving "
            "every claim and required phrase.\n"
            "- A narrow synonym substitution or phrase replacement is not a "
            "deep reconstruction.\n"
            "- Do not return commentary, explanations, headings, or notes.\n"
            "- Return only the structured response required by the schema.\n\n"
            "SOURCE TEXT:\n"
            f"{request.text}\n\n"
            "REJECTED REWRITE:\n"
            f"{rejected_text}"
        )

    @staticmethod
    def _user_prompt(request: RewriteRequest) -> str:
        return (
            f"Document type: {request.document_type.value}\n"
            f"Audience: {request.audience}\n"
            f"Tone: {request.tone}\n"
            f"Rewrite intensity: {request.intensity.value}\n"
            "Interpret rewrite intensity as permission to change structure and "
            "wording only. It never permits stronger qualifications, broader "
            "scope, greater ownership, increased certainty, invented outcomes, "
            "or additional claims.\n"
            f"Preserve numbers: {request.preserve_numbers}\n"
            f"Preserve dates: {request.preserve_dates}\n\n"
            "Source text:\n"
            f"{request.text}"
        )


def _extract_usage(response_body: dict[str, Any]) -> ProviderUsage:
    result = response_body.get("result")

    if not isinstance(result, dict):
        return ProviderUsage()

    usage = result.get("usage")

    if not isinstance(usage, dict):
        return ProviderUsage()

    input_tokens = _optional_non_negative_integer(
        usage.get("input_tokens", usage.get("prompt_tokens"))
    )
    output_tokens = _optional_non_negative_integer(
        usage.get("output_tokens", usage.get("completion_tokens"))
    )
    total_tokens = _optional_non_negative_integer(usage.get("total_tokens"))

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return ProviderUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _merge_usage(
    first: ProviderUsage,
    second: ProviderUsage,
) -> ProviderUsage:
    return ProviderUsage(
        input_tokens=_sum_optional_values(
            first.input_tokens,
            second.input_tokens,
        ),
        output_tokens=_sum_optional_values(
            first.output_tokens,
            second.output_tokens,
        ),
        total_tokens=_sum_optional_values(
            first.total_tokens,
            second.total_tokens,
        ),
    )


def _sum_optional_values(
    first: int | None,
    second: int | None,
) -> int | None:
    if first is None and second is None:
        return None

    return (first or 0) + (second or 0)


def _optional_non_negative_integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int) and value >= 0:
        return value

    return None


def _parse_json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise RewriteProviderResponseError("Cloudflare Workers AI returned non-JSON data.") from exc

    if not isinstance(body, dict):
        raise RewriteProviderResponseError(
            "Cloudflare Workers AI returned an unexpected response type."
        )

    return body


def _extract_generated_output(response_body: dict[str, Any]) -> Any:
    result = response_body.get("result")

    if not isinstance(result, dict):
        raise RewriteProviderResponseError("Cloudflare response did not contain a result object.")

    response_value = result.get("response")

    if response_value is not None:
        return response_value

    output_text = result.get("output_text")

    if isinstance(output_text, str) and output_text.strip():
        return output_text

    choices = result.get("choices")

    if isinstance(choices, list):
        extracted_text = _extract_text_from_chat_completions(choices)

        if extracted_text is not None:
            return extracted_text

    output = result.get("output")

    if isinstance(output, list):
        extracted_text = _extract_text_from_responses_output(output)

        if extracted_text is not None:
            return extracted_text

    raise RewriteProviderResponseError(
        "Cloudflare response did not contain generated text in a supported format."
    )


def _extract_text_from_chat_completions(
    choices: list[Any],
) -> str | None:
    for choice in choices:
        if not isinstance(choice, dict):
            continue

        message = choice.get("message")

        if not isinstance(message, dict):
            continue

        content = message.get("content")

        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            fragments: list[str] = []

            for item in content:
                if not isinstance(item, dict):
                    continue

                item_text = item.get("text")

                if isinstance(item_text, str) and item_text.strip():
                    fragments.append(item_text.strip())

            if fragments:
                return "\n".join(fragments)

    return None


def _extract_text_from_responses_output(output: list[Any]) -> str | None:
    text_fragments: list[str] = []

    for item in output:
        if not isinstance(item, dict):
            continue

        item_text = item.get("text")

        if isinstance(item_text, str) and item_text.strip():
            text_fragments.append(item_text.strip())

        content = item.get("content")

        if not isinstance(content, list):
            continue

        for content_item in content:
            if not isinstance(content_item, dict):
                continue

            content_text = content_item.get("text")

            if isinstance(content_text, str) and content_text.strip():
                text_fragments.append(content_text.strip())

            output_text = content_item.get("output_text")

            if isinstance(output_text, str) and output_text.strip():
                text_fragments.append(output_text.strip())

    if not text_fragments:
        return None

    return "\n".join(text_fragments)


def _parse_rewritten_text(generated_output: Any) -> str:
    if isinstance(generated_output, dict):
        rewritten_text = generated_output.get("rewritten_text")

        if not isinstance(rewritten_text, str) or not rewritten_text.strip():
            raise RewriteProviderResponseError(
                "Cloudflare structured output did not contain rewritten_text."
            )

        return rewritten_text.strip()

    if not isinstance(generated_output, str):
        raise RewriteProviderResponseError("Cloudflare generated output had an unsupported type.")

    normalized = generated_output.strip()

    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```")
        normalized = normalized.removesuffix("```").strip()

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise RewriteProviderResponseError("Cloudflare model output was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise RewriteProviderResponseError("Cloudflare model output must be a JSON object.")

    rewritten_text = parsed.get("rewritten_text")

    if not isinstance(rewritten_text, str) or not rewritten_text.strip():
        raise RewriteProviderResponseError(
            "Cloudflare model output did not contain rewritten_text."
        )

    return rewritten_text.strip()


def _safe_error_detail(response: httpx.Response) -> str:
    text = response.text.strip()

    if not text:
        return "No response details were returned."

    return text[:500]
