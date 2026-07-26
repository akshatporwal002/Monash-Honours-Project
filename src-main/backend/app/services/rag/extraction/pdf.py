"""Page-preserving PDF text extraction."""

from __future__ import annotations

from typing import BinaryIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.services.rag.contracts import ExtractedBlock, ExtractedDocument
from app.services.rag.errors import EncryptedDocumentError, InvalidDocumentError
from app.services.rag.extraction.base import document_from_blocks


class PdfDocumentExtractor:
    supported_mime_types = frozenset({"application/pdf"})

    def extract(self, source: BinaryIO) -> ExtractedDocument:
        try:
            source.seek(0)
            reader = PdfReader(source)
            if reader.is_encrypted and reader.decrypt("") == 0:
                raise EncryptedDocumentError()
            blocks = []
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    blocks.append(
                        ExtractedBlock(
                            ordinal=len(blocks),
                            text=text,
                            heading=None,
                            location_label=f"Page {page_number}",
                            block_type="paragraph",
                        )
                    )
            metadata_title = getattr(reader.metadata, "title", None) if reader.metadata else None
            return document_from_blocks(blocks, metadata_title)
        except EncryptedDocumentError:
            raise
        except PdfReadError as error:
            raise InvalidDocumentError() from error
