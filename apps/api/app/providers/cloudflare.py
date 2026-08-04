from __future__ import annotations

import json
from time import perf_counter
from typing import Any

import httpx

from app.domain.models import RewriteChange, RewriteRequest
from app.providers.base import ProviderUsage, RewriteProviderResult
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)

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

        try:
            if self._client is not None:
                response = self._client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
            else:
                with httpx.Client() as client:
                    response = client.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=self._timeout_seconds,
                    )
        except httpx.HTTPError as exc:
            raise RewriteProviderTransportError("Cloudflare Workers AI request failed.") from exc

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

        changes: list[RewriteChange] = []

        if rewritten_text != request.text:
            changes.append(
                RewriteChange(
                    change_id="change-cloudflare-1",
                    original=request.text,
                    replacement=rewritten_text,
                    reason=(
                        "Cloudflare Workers AI reconstructed the draft using "
                        "the requested audience, tone, and rewrite intensity."
                    ),
                    change_type="model_reconstruction",
                )
            )

        return RewriteProviderResult(
            text=rewritten_text,
            changes=changes,
            provider_name=self.provider_name,
            model_name=self._model_name,
            prompt_version="cloudflare-humanize-v2",
            latency_ms=round((perf_counter() - started_at) * 1000, 3),
            primary_provider_name=self.provider_name,
            fallback_used=False,
            provider_error_category=None,
            usage=usage,
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a controlled editorial reconstruction engine. "
            "Rewrite text so it sounds natural, direct, and context-aware. "
            "Preserve the original meaning. Preserve every name, number, "
            "date, metric, citation, technical term, qualification, and "
            "negation exactly unless the user explicitly asks otherwise. "
            "Do not add facts, achievements, experiences, citations, or "
            "claims. Remove formulaic AI phrasing, repetitive transitions, "
            "empty intensifiers, and robotic sentence symmetry. "
            "Return only the structured response requested by the schema."
        )

    @staticmethod
    def _user_prompt(request: RewriteRequest) -> str:
        return (
            f"Document type: {request.document_type.value}\n"
            f"Audience: {request.audience}\n"
            f"Tone: {request.tone}\n"
            f"Rewrite intensity: {request.intensity.value}\n"
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
