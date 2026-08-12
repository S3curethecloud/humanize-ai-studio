from __future__ import annotations

import hashlib

from app.v2.domain.long_documents import (
    DocumentSection,
    DocumentStructure,
)

DOCUMENT_STRUCTURE_DETECTOR_VERSION = "document-structure-v1"


class DocumentStructureDetector:
    version = DOCUMENT_STRUCTURE_DETECTOR_VERSION

    def detect(
        self,
        *,
        source_text: str,
    ) -> DocumentStructure:
        if not source_text:
            raise ValueError("source_text must not be empty")

        structure_id = self._structure_id(
            source_text=source_text,
        )

        heading_markers = self._heading_markers(
            source_text=source_text,
        )

        if not heading_markers:
            return DocumentStructure(
                structure_id=structure_id,
                source_text=source_text,
                sections=(
                    DocumentSection(
                        section_id=(f"{structure_id}-section-1"),
                        ordinal=1,
                        start_offset=0,
                        end_offset=len(source_text),
                        source_text=source_text,
                        heading=None,
                        eligible_for_rewrite=True,
                    ),
                ),
            )

        boundaries: list[tuple[int, str | None]] = []

        first_heading_offset = heading_markers[0][0]

        if first_heading_offset > 0:
            boundaries.append(
                (
                    0,
                    None,
                )
            )

        boundaries.extend(heading_markers)

        sections: list[DocumentSection] = []

        for index, (
            start_offset,
            heading,
        ) in enumerate(boundaries):
            if index + 1 < len(boundaries):
                end_offset = boundaries[index + 1][0]
            else:
                end_offset = len(source_text)

            ordinal = index + 1

            sections.append(
                DocumentSection(
                    section_id=(f"{structure_id}-section-{ordinal}"),
                    ordinal=ordinal,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    source_text=source_text[start_offset:end_offset],
                    heading=heading,
                    eligible_for_rewrite=True,
                )
            )

        return DocumentStructure(
            structure_id=structure_id,
            source_text=source_text,
            sections=tuple(sections),
        )

    def _heading_markers(
        self,
        *,
        source_text: str,
    ) -> tuple[
        tuple[int, str],
        ...,
    ]:
        markers: list[tuple[int, str]] = []

        offset = 0

        for line in source_text.splitlines(
            keepends=True,
        ):
            heading = self._heading_from_line(
                line=line,
            )

            if heading is not None:
                markers.append(
                    (
                        offset,
                        heading,
                    )
                )

            offset += len(line)

        return tuple(markers)

    def _heading_from_line(
        self,
        *,
        line: str,
    ) -> str | None:
        content = line.rstrip("\r\n")

        marker_count = 0

        while marker_count < len(content) and marker_count < 6 and content[marker_count] == "#":
            marker_count += 1

        if marker_count == 0:
            return None

        if marker_count < len(content) and content[marker_count] == "#":
            return None

        if marker_count >= len(content):
            return None

        separator = content[marker_count]

        if separator not in {
            " ",
            "\t",
        }:
            return None

        heading = content[marker_count:].strip()

        if not heading:
            return None

        return heading

    def _structure_id(
        self,
        *,
        source_text: str,
    ) -> str:
        canonical = (f"{self.version}\0{source_text}").encode()

        digest = hashlib.sha256(canonical).hexdigest()[:24]

        return f"document-structure-{digest}"
