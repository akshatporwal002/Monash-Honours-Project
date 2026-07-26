"""Order-preserving DOCX text and table extraction."""

from __future__ import annotations

from typing import BinaryIO

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.services.rag.contracts import ExtractedBlock, ExtractedDocument
from app.services.rag.errors import InvalidDocumentError
from app.services.rag.extraction.base import document_from_blocks, validate_openxml_archive


class DocxDocumentExtractor:
    supported_mime_types = frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    )

    def extract(self, source: BinaryIO) -> ExtractedDocument:
        validate_openxml_archive(source, "word/")
        try:
            document = Document(source)
            heading: str | None = None
            blocks: list[ExtractedBlock] = []
            for item in document.iter_inner_content():
                if isinstance(item, Paragraph):
                    text = item.text.strip()
                    if not text:
                        continue
                    if item.style and item.style.name.startswith("Heading"):
                        heading = text
                        blocks.append(
                            ExtractedBlock(
                                len(blocks), text, heading, f"Heading: {heading}", "heading"
                            )
                        )
                    else:
                        blocks.append(
                            ExtractedBlock(
                                len(blocks),
                                text,
                                heading,
                                f"Heading: {heading}" if heading else "Document body",
                                "paragraph",
                            )
                        )
                elif isinstance(item, Table):
                    text = self._table_text(item)
                    if text:
                        blocks.append(
                            ExtractedBlock(
                                len(blocks),
                                text,
                                heading,
                                f"Heading: {heading}" if heading else "Document body",
                                "table",
                            )
                        )
            return document_from_blocks(blocks, document.core_properties.title)
        except (KeyError, ValueError, OSError) as error:
            raise InvalidDocumentError() from error

    @staticmethod
    def _table_text(table: Table) -> str:
        rows: list[str] = []
        for row in table.rows:
            seen_cells: set[int] = set()
            cells: list[str] = []
            for cell in row.cells:
                cell_identity = id(cell._tc)
                if cell_identity in seen_cells:
                    continue
                seen_cells.add(cell_identity)
                value = cell.text.strip()
                if value:
                    cells.append(value)
            if cells:
                rows.append(" | ".join(cells))
        return "\n".join(rows)
