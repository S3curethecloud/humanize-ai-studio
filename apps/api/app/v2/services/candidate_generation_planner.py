from __future__ import annotations

import hashlib
import json

from app.domain.models import RewriteRequest
from app.v2.domain.candidate_generation import (
    CandidateGenerationPlan,
    CandidateGenerationStrategy,
    CandidateGenerationVariant,
)

CANDIDATE_GENERATION_PLAN_VERSION = "candidate-generation-plan-v1"

_STRATEGIES = (
    (
        CandidateGenerationStrategy.BALANCED,
        (
            "Generate a distinct candidate using balanced natural "
            "phrasing without changing the requested tone, meaning, "
            "facts, or rewrite constraints."
        ),
    ),
    (
        CandidateGenerationStrategy.CONCISE,
        (
            "Generate a distinct candidate using tighter phrasing and "
            "cleaner sentence boundaries where compatible with the "
            "requested tone and rewrite constraints."
        ),
    ),
    (
        CandidateGenerationStrategy.STRUCTURAL,
        (
            "Generate a distinct candidate by varying sentence "
            "structure and clause ordering while preserving meaning, "
            "facts, tone, and rewrite constraints."
        ),
    ),
    (
        CandidateGenerationStrategy.FLOW,
        (
            "Generate a distinct candidate emphasizing natural cadence "
            "and smooth flow without changing meaning, facts, tone, or "
            "rewrite constraints."
        ),
    ),
    (
        CandidateGenerationStrategy.DIRECT,
        (
            "Generate a distinct candidate using clearer direct "
            "phrasing where compatible with the requested tone while "
            "preserving meaning, facts, and rewrite constraints."
        ),
    ),
)


class CandidateGenerationPlanner:
    version = CANDIDATE_GENERATION_PLAN_VERSION

    def plan(
        self,
        *,
        request: RewriteRequest,
        candidate_count: int = 3,
    ) -> CandidateGenerationPlan:
        if not 2 <= candidate_count <= 5:
            raise ValueError("candidate_count must be between 2 and 5")

        candidate_set_id = self._candidate_set_id(
            request=request,
            candidate_count=candidate_count,
        )

        variants = tuple(
            CandidateGenerationVariant(
                candidate_id=(f"{candidate_set_id}-candidate-{ordinal}"),
                ordinal=ordinal,
                strategy=strategy,
                instruction=instruction,
            )
            for ordinal, (
                strategy,
                instruction,
            ) in enumerate(
                _STRATEGIES[:candidate_count],
                start=1,
            )
        )

        return CandidateGenerationPlan(
            plan_version=self.version,
            candidate_set_id=candidate_set_id,
            candidate_count=candidate_count,
            variants=variants,
        )

    def _candidate_set_id(
        self,
        *,
        request: RewriteRequest,
        candidate_count: int,
    ) -> str:
        payload = {
            "plan_version": self.version,
            "candidate_count": candidate_count,
            "rewrite_request": request.model_dump(mode="json"),
        }

        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        digest = hashlib.sha256(canonical).hexdigest()[:24]

        return f"candidate-set-{digest}"
