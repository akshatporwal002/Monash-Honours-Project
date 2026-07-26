"""Conservative normalisation that preserves technical content."""

from __future__ import annotations

import re
import unicodedata

from app.services.rag.errors import ExtractedContentTooLargeError

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_SPACE = re.compile(r"[^\S\r\n]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = _HORIZONTAL_SPACE.sub(" ", text)
    return _BLANK_LINES.sub("\n\n", text).strip()


def ensure_document_size(texts: list[str], maximum_characters: int) -> None:
    if sum(len(text) for text in texts) > maximum_characters:
        raise ExtractedContentTooLargeError()
