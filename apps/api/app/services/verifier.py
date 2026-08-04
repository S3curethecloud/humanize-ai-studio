from __future__ import annotations

from collections import Counter

from app.domain.models import (
    ProtectedFact,
    ReleaseDecision,
    VerificationResult,
)
from app.services.fact_extractor import DATE_PATTERN, NUMBER_PATTERN
from app.services.fact_normalization import normalize_fact_text


class RewriteVerifier:
    def verify(
        self,
        source_text: str,
        rewritten_text: str,
        protected_facts: list[ProtectedFact],
    ) -> VerificationResult:
        del source_text

        normalized_rewrite = normalize_fact_text(rewritten_text)

        preserved: list[str] = []
        missing: list[str] = []

        for fact in protected_facts:
            normalized_value = normalize_fact_text(fact.value)

            if normalized_value in normalized_rewrite:
                preserved.append(fact.fact_id)
            else:
                missing.append(fact.fact_id)

        expected_values = Counter(normalize_fact_text(fact.value) for fact in protected_facts)

        rewritten_date_matches = list(DATE_PATTERN.finditer(normalized_rewrite))
        rewritten_date_ranges = [(match.start(), match.end()) for match in rewritten_date_matches]

        rewritten_values = Counter(match.group(0) for match in rewritten_date_matches)

        for match in NUMBER_PATTERN.finditer(normalized_rewrite):
            number_is_inside_date = any(
                start <= match.start() and match.end() <= end
                for start, end in rewritten_date_ranges
            )

            if number_is_inside_date:
                continue

            rewritten_values[match.group(0)] += 1

        unexpected: list[str] = []

        for value, count in rewritten_values.items():
            expected_count = expected_values.get(value, 0)

            if count > expected_count:
                unexpected.extend([value] * (count - expected_count))

        warnings: list[str] = []

        if missing:
            warnings.append("One or more protected facts were removed or changed.")

        if unexpected:
            warnings.append("The rewrite introduced numbers or dates not present in the source.")

        if missing:
            decision = ReleaseDecision.FAIL
        elif unexpected:
            decision = ReleaseDecision.WARN
        else:
            decision = ReleaseDecision.PASS

        return VerificationResult(
            decision=decision,
            preserved_facts=preserved,
            missing_facts=missing,
            unexpected_facts=unexpected,
            warnings=warnings,
        )
