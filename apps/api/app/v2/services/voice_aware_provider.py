from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.domain.models import RewriteRequest
from app.providers.base import (
    RewriteProvider,
    RewriteProviderResult,
)
from app.v2.domain.voice_rewrite import (
    VoiceRewriteGuidance,
)


class VoiceAwareRewriteProvider:
    def __init__(
        self,
        *,
        provider: RewriteProvider,
    ) -> None:
        self._provider = provider
        self._guidance: ContextVar[VoiceRewriteGuidance | None] = ContextVar(
            "voice_rewrite_guidance",
            default=None,
        )

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @contextmanager
    def use_guidance(
        self,
        guidance: VoiceRewriteGuidance,
    ) -> Iterator[None]:
        token = self._guidance.set(guidance)

        try:
            yield
        finally:
            self._guidance.reset(token)

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        guidance = self._guidance.get()

        if guidance is None:
            return self._provider.rewrite(request)

        provider_request = request.model_copy(
            update={
                "tone": self._provider_tone(
                    original_tone=request.tone,
                    guidance=guidance,
                )
            }
        )

        return self._provider.rewrite(provider_request)

    def _provider_tone(
        self,
        *,
        original_tone: str,
        guidance: VoiceRewriteGuidance,
    ) -> str:
        voice_lines = "\n".join(
            (f"- {instruction.attribute}={instruction.value}: {instruction.instruction}")
            for instruction in guidance.instructions
        )

        return (
            f"{original_tone}\n\n"
            "VOICE DNA GUIDANCE "
            f"({guidance.guidance_version}):\n"
            f"{voice_lines}\n\n"
            "VOICE AUTHORITY CONSTRAINT:\n"
            f"{guidance.guardrails.policy_statement}"
        )
