"""Deterministic heading-aware, token-bounded chunk generation."""

from __future__ import annotations

import hashlib
import re

from app.services.rag.contracts import ChunkDraft, ExtractedBlock, TokenCounter
from app.services.rag.normalisation import normalise_text


class WhitespaceTokenCounter:
    def count(self, text: str) -> int:
        return len(re.findall(r"\S+", text))

    def split_to_token_limit(self, text: str, limit: int) -> list[str]:
        tokens = re.findall(r"\S+", text)
        return [" ".join(tokens[index : index + limit]) for index in range(0, len(tokens), limit)]


class HeadingAwareChunker:
    def __init__(self, counter: TokenCounter, target_tokens: int, max_tokens: int, overlap_tokens: int) -> None:
        self.counter = counter
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, blocks: tuple[ExtractedBlock, ...]) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        current: list[str] = []
        current_heading: str | None = None
        current_location = ""

        def flush() -> None:
            if not current:
                return
            text = "\n\n".join(current).strip()
            if self.counter.count(text) >= 5:
                drafts.append(self._draft(len(drafts), text, current_heading, current_location))
            current.clear()

        for block in blocks:
            text = normalise_text(block.text)
            if not text:
                continue
            if current and block.heading != current_heading:
                flush()
            if not current:
                current_heading, current_location = block.heading, block.location_label
            for part in self._split(text):
                proposed = "\n\n".join([*current, part])
                if current and self.counter.count(proposed) > self.target_tokens:
                    flush()
                    current_heading, current_location = block.heading, block.location_label
                current.append(part)
                if self.counter.count("\n\n".join(current)) >= self.max_tokens:
                    flush()
                    current_heading, current_location = block.heading, block.location_label
        flush()
        return drafts

    def _split(self, text: str) -> list[str]:
        if self.counter.count(text) <= self.max_tokens:
            return [text]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current} {sentence}".strip()
            if current and self.counter.count(candidate) > self.max_tokens:
                pieces.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            pieces.append(current)
        return [subpiece for piece in pieces for subpiece in self.counter.split_to_token_limit(piece, self.max_tokens)]

    def _draft(self, index: int, text: str, heading: str | None, location: str) -> ChunkDraft:
        return ChunkDraft(
            chunk_index=index,
            text=text,
            heading=heading,
            location_label=location,
            token_count=self.counter.count(text),
            chunk_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
