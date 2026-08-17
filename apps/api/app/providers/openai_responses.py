from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from app.domain.models import (
    RewriteChange,
    RewriteRequest,
)
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)

OPENAI_PROVIDER_NAME = "openai"
OPENAI_RESPONSES_URL = (
    "https://api.openai.com/v1/responses"
)


class OpenAIResponsesProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise RewriteProviderConfigurationError(
                "OpenAI API key must not be empty."
            )

        if not model_name.strip():
            raise RewriteProviderConfigurationError(
                "OpenAI model name must not be empty."
            )

        if timeout_seconds <= 0:
            raise RewriteProviderConfigurationError(
                "OpenAI timeout must be greater than zero."
            )

        self._api_key = api_key.strip()
        self._model_name = model_name.strip()
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def provider_name(self) -> str:
        return OPENAI_PROVIDER_NAME

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        started_at = perf_counter()

        response = self._post(
            payload={
                "model": self._model_name,
                "input": self._build_input(request),
                "store": False,
            }
        )

        if response.is_error:
            raise RewriteProviderResponseError(
                "OpenAI Responses API returned "
                f"HTTP {response.status_code}: "
                f"{_safe_error_detail(response)}"
            )

        body = _parse_json_object(response)
        rewritten_text = _extract_output_text(body)
        usage = _extract_usage(body)

        changes: list[RewriteChange] = []

        if rewritten_text != request.text:
            changes.append(
                RewriteChange(
                    change_id="change-openai-1",
                    original=request.text,
                    replacement=rewritten_text,
                    reason=(
                        "OpenAI reconstructed the draft "
                        "under the requested rewrite controls."
                    ),
                    change_type="model_reconstruction",
                )
            )

        return RewriteProviderResult(
            text=rewritten_text,
            changes=changes,
            provider_name=self.provider_name,
            model_name=self._model_name,
            prompt_version="openai-humanize-v1",
            latency_ms=round(
                (perf_counter() - started_at) * 1000,
                3,
            ),
            primary_provider_name=self.provider_name,
            fallback_used=False,
            provider_error_category=None,
            usage=usage,
        )

    def _post(
        self,
        *,
        payload: dict[str, Any],
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            if self._client is not None:
                return self._client.post(
                    OPENAI_RESPONSES_URL,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )

            with httpx.Client() as client:
                return client.post(
                    OPENAI_RESPONSES_URL,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )
        except httpx.HTTPError as exc:
            raise RewriteProviderTransportError(
                "OpenAI Responses API request failed."
            ) from exc

    @staticmethod
    def _build_input(
        request: RewriteRequest,
    ) -> list[dict[str, Any]]:
        instructions = (
            "Rewrite the supplied text so it sounds natural, "
            "clear, and appropriate for the requested audience. "
            "Preserve every factual claim, name, number, date, "
            "qualification, limitation, negation, level of "
            "certainty, ownership boundary, and scope boundary. "
            "Do not invent achievements, expertise, authority, "
            "metrics, outcomes, or responsibilities. "
            "Return only the rewritten text."
        )

        user_text = (
            f"Audience: {request.audience}\n"
            f"Tone: {request.tone}\n"
            f"Rewrite intensity: {request.intensity.value}\n\n"
            "SOURCE TEXT:\n"
            f"{request.text}"
        )

        return [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": instructions,
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_text,
                    }
                ],
            },
        ]


def _parse_json_object(
    response: httpx.Response,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RewriteProviderResponseError(
            "OpenAI Responses API returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise RewriteProviderResponseError(
            "OpenAI Responses API returned "
            "a non-object response."
        )

    return payload


def _extract_output_text(
    payload: dict[str, Any],
) -> str:
    output = payload.get("output")

    if not isinstance(output, list):
        raise RewriteProviderResponseError(
            "OpenAI response does not contain "
            "a valid output collection."
        )

    text_parts: list[str] = []

    for item in output:
        if not isinstance(item, dict):
            continue

        if item.get("type") != "message":
            continue

        content = item.get("content")

        if not isinstance(content, list):
            continue

        for content_item in content:
            if not isinstance(content_item, dict):
                continue

            if content_item.get("type") != "output_text":
                continue

            text = content_item.get("text")

            if isinstance(text, str) and text:
                text_parts.append(text)

    rewritten_text = "".join(text_parts).strip()

    if not rewritten_text:
        raise RewriteProviderResponseError(
            "OpenAI response does not contain output text."
        )

    return rewritten_text


def _extract_usage(
    payload: dict[str, Any],
) -> ProviderUsage:
    usage = payload.get("usage")

    if not isinstance(usage, dict):
        return ProviderUsage()

    return ProviderUsage(
        input_tokens=_optional_non_negative_int(
            usage.get("input_tokens")
        ),
        output_tokens=_optional_non_negative_int(
            usage.get("output_tokens")
        ),
        total_tokens=_optional_non_negative_int(
            usage.get("total_tokens")
        ),
    )


def _optional_non_negative_int(
    value: object,
) -> int | None:
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    ):
        return value

    return None


def _safe_error_detail(
    response: httpx.Response,
) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:500]

    if isinstance(payload, dict):
        error = payload.get("error")

        if isinstance(error, dict):
            message = error.get("message")

            if isinstance(message, str):
                return message[:500]

    return str(payload)[:500]
