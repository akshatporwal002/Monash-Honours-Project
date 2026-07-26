"""Shared validation helpers for structured document extraction."""

from __future__ import annotations

import zipfile
from collections.abc import Iterable
from typing import BinaryIO

from app.services.rag.contracts import ExtractedBlock, ExtractedDocument
from app.services.rag.errors import InvalidDocumentError, NoExtractableTextError

MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 100


def validate_openxml_archive(source: BinaryIO, required_prefix: str) -> None:
    """Validate an OOXML archive before its parser expands it."""
    try:
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            total_uncompressed = sum(entry.file_size for entry in entries)
            total_compressed = sum(entry.compress_size for entry in entries)
            if len(entries) > MAX_ZIP_ENTRIES or total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise InvalidDocumentError()
            if total_uncompressed and (
                total_compressed == 0
                or total_uncompressed / total_compressed > MAX_ZIP_COMPRESSION_RATIO
            ):
                raise InvalidDocumentError()
            names = archive.namelist()
            if "[Content_Types].xml" not in names or not any(
                name.startswith(required_prefix) for name in names
            ):
                raise InvalidDocumentError()
    except zipfile.BadZipFile as error:
        raise InvalidDocumentError() from error
    finally:
        source.seek(0)


def document_from_blocks(blocks: Iterable[ExtractedBlock], title: str | None) -> ExtractedDocument:
    retained = tuple(block for block in blocks if block.text.strip())
    if not retained:
        raise NoExtractableTextError()
    return ExtractedDocument(
        blocks=retained,
        title=title.strip() if title and title.strip() else None,
        character_count=sum(len(block.text) for block in retained),
    )
