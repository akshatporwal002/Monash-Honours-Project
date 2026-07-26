"""Conservative HTML text extraction for trusted HTTPS responses."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import BinaryIO, ClassVar

from app.services.rag.contracts import ExtractedBlock, ExtractedDocument
from app.services.rag.extraction.base import document_from_blocks


class _HtmlTextParser(HTMLParser):
    ignored: ClassVar[set[str]] = {"script", "style", "nav", "form", "noscript"}
    retained: ClassVar[set[str]] = {
        "p",
        "li",
        "pre",
        "code",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, str]] = []
        self.current_tag: str | None = None
        self.current: list[str] = []
        self.ignore_depth = 0
        self.title: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.ignored:
            self.ignore_depth += 1
        if not self.ignore_depth and tag in self.retained | {"title"}:
            self.current_tag, self.current = tag, []

    def handle_data(self, data: str) -> None:
        if not self.ignore_depth and self.current_tag:
            self.current.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored and self.ignore_depth:
            self.ignore_depth -= 1
        if tag == self.current_tag:
            value = "".join(self.current).strip()
            if tag == "title":
                self.title = value or None
            elif value:
                self.blocks.append((tag, value))
            self.current_tag, self.current = None, []


class HtmlDocumentExtractor:
    supported_mime_types = frozenset({"text/html"})

    def extract(self, source: BinaryIO) -> ExtractedDocument:
        parser = _HtmlTextParser()
        parser.feed(source.read().decode("utf-8", errors="replace"))
        heading: str | None = None
        blocks: list[ExtractedBlock] = []
        for tag, text in parser.blocks:
            if tag.startswith("h"):
                heading = text
                block_type = "heading"
            elif tag in {"pre", "code"}:
                block_type = "code"
            elif tag in {"td", "th"}:
                block_type = "table"
            else:
                block_type = "paragraph"
            blocks.append(
                ExtractedBlock(
                    len(blocks), text, heading, f"Web section: {heading or 'Page'}", block_type
                )
            )
        return document_from_blocks(blocks, parser.title)
