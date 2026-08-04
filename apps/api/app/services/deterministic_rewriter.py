from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.models import RewriteChange

REPLACEMENTS = (
    (
        r"\bFurthermore,\s*",
        "",
        "Removed an unnecessary formal transition.",
        "naturalness",
    ),
    (
        r"\bMoreover,\s*",
        "",
        "Removed an unnecessary formal transition.",
        "naturalness",
    ),
    (
        r"\bAdditionally,\s*",
        "",
        "Removed an unnecessary formal transition.",
        "naturalness",
    ),
    (
        r"\b[Ii]t is important to note that\s+",
        "",
        "Removed a filler phrase and made the statement direct.",
        "clarity",
    ),
    (
        r"\b[Ii]n conclusion,\s*",
        "",
        "Removed a predictable conclusion marker.",
        "naturalness",
    ),
    (
        r"\b[Ii]n today's rapidly evolving technological landscape,\s*",
        "",
        "Removed a generic opening phrase.",
        "clarity",
    ),
)


@dataclass(frozen=True)
class DeterministicRewriteResult:
    text: str
    changes: list[RewriteChange]


class DeterministicRewriter:
    def rewrite(self, text: str) -> DeterministicRewriteResult:
        rewritten = text
        changes: list[RewriteChange] = []

        for index, (pattern, replacement, reason, change_type) in enumerate(
            REPLACEMENTS,
            start=1,
        ):
            match = re.search(pattern, rewritten)

            if not match:
                continue

            original = match.group(0)
            rewritten = re.sub(pattern, replacement, rewritten)

            changes.append(
                RewriteChange(
                    change_id=f"change-{index}",
                    original=original,
                    replacement=replacement,
                    reason=reason,
                    change_type=change_type,
                )
            )

        rewritten = re.sub(r"[ \t]{2,}", " ", rewritten)
        rewritten = re.sub(r"\s+([,.!?])", r"\1", rewritten)
        rewritten = rewritten.strip()

        if rewritten:
            rewritten = rewritten[0].upper() + rewritten[1:]

        return DeterministicRewriteResult(
            text=rewritten,
            changes=changes,
        )
