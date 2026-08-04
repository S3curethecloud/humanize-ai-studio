from __future__ import annotations

import re

from app.domain.models import ProtectedFact, TextSpan
from app.services.fact_normalization import normalize_fact_text

NUMBER_PATTERN = re.compile(r"\b(?:\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|\d+(?:\.\d+)?%)\b")

MONTH_PATTERN = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)

DATE_PATTERN = re.compile(
    rf"\b(?:{MONTH_PATTERN}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)


class FactExtractor:
    def extract(
        self,
        text: str,
        *,
        preserve_numbers: bool,
        preserve_dates: bool,
    ) -> list[ProtectedFact]:
        normalized_text = normalize_fact_text(text)
        facts: list[ProtectedFact] = []

        if preserve_dates:
            for index, match in enumerate(
                DATE_PATTERN.finditer(normalized_text),
                start=1,
            ):
                facts.append(
                    ProtectedFact(
                        fact_id=f"date-{index}",
                        value=match.group(0),
                        fact_type="date",
                        source_span=TextSpan(
                            start=match.start(),
                            end=match.end(),
                        ),
                    )
                )

        if preserve_numbers:
            date_ranges = {
                (fact.source_span.start, fact.source_span.end)
                for fact in facts
                if fact.fact_type == "date"
            }

            number_index = 1

            for match in NUMBER_PATTERN.finditer(normalized_text):
                number_is_inside_date = any(
                    start <= match.start() and match.end() <= end for start, end in date_ranges
                )

                if number_is_inside_date:
                    continue

                facts.append(
                    ProtectedFact(
                        fact_id=f"number-{number_index}",
                        value=match.group(0),
                        fact_type="number",
                        source_span=TextSpan(
                            start=match.start(),
                            end=match.end(),
                        ),
                    )
                )
                number_index += 1

        return facts
