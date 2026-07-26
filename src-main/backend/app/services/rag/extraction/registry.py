"""MIME-type registry for document extractors."""

from __future__ import annotations

from collections.abc import Iterable

from app.services.rag.contracts import DocumentExtractor
from app.services.rag.errors import UnsupportedMaterialTypeError


class ExtractorRegistry:
    def __init__(self, extractors: Iterable[DocumentExtractor]) -> None:
        self._extractors = {
            mime_type: extractor
            for extractor in extractors
            for mime_type in extractor.supported_mime_types
        }

    def get(self, mime_type: str) -> DocumentExtractor:
        try:
            return self._extractors[mime_type]
        except KeyError as error:
            raise UnsupportedMaterialTypeError() from error
