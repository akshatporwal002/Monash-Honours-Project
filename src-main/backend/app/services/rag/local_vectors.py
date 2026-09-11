"""Deterministic text vectors and a disposable, persistent SQLite vector cache.

No trained model, network access, downloads or semantic-quality claim. The cache
holds only vectors; source text and authorization always come from the main DB.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from app.services.rag.normalisation import normalise_text

_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset("a an and apply describe explain for how in of the to what".split())


def text_fragments(text: str) -> tuple[str, ...]:
    return tuple(
        fragment
        for fragment in dict.fromkeys(
            [
                text,
                *re.split(r"(?<=[.!?])\s+|\n+", text),
            ]
        )
        if fragment.strip()
    )


class LocalTextEmbedding:
    """L2-normalized, signed word-frequency hashing with stable SHA-256 buckets."""

    dimension = 2048
    model_id = "local-word-hash-2048-sentences-v1"

    def embed_query(self, text: str) -> list[float]:
        terms = Counter(_WORDS.findall(normalise_text(text).casefold()))
        useful = {term: count for term, count in terms.items() if term not in _STOP}
        vector = [0.0] * self.dimension
        for term, count in (useful or terms).items():
            digest = hashlib.sha256(term.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:8], "big") % self.dimension
            sign = 1 if digest[8] & 1 else -1
            vector[bucket] += sign * (1 + math.log(count))
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_documents(self, texts) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class SqliteVectorCache:
    """Rebuild missing/invalid rows; a corrupt/unavailable DB fails explicitly.

    Keys include the model, frozen source identity and exact text digest. SQLite
    serializes independent API/worker writers. No cache row supplies a source ID,
    text, approval, scan state or scope to a retrieval result.
    """

    def __init__(self, path: Path, embedding: LocalTextEmbedding):
        self.path, self.embedding = path, embedding

    def vectors(self, sources) -> list[list[list[float]]]:
        if not sources:
            return []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=5)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS vectors ("
                "cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            vectors = []
            for passage, revision, _ in sources:
                identity = [
                    self.embedding.model_id,
                    passage.id,
                    revision.id,
                    revision.course_id,
                    revision.content_hash,
                    hashlib.sha256(passage.chunk_text.encode()).hexdigest(),
                ]
                # Whole passage and sentence vectors share the original passage ID.
                # Long, mixed-topic chunks should not dilute a relevant sentence.
                fragments = text_fragments(passage.chunk_text)
                passage_vectors = []
                for fragment in fragments:
                    if not fragment.strip():
                        continue
                    key = hashlib.sha256(json.dumps([*identity, fragment]).encode()).hexdigest()
                    row = connection.execute(
                        "SELECT payload, digest FROM vectors WHERE cache_key=?", (key,)
                    ).fetchone()
                    vector = self._read(row)
                    if vector is None:
                        vector = self.embedding.embed_documents([fragment])[0]
                        payload = json.dumps(vector, separators=(",", ":"), allow_nan=False)
                        connection.execute(
                            "INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)",
                            (key, payload, hashlib.sha256(payload.encode()).hexdigest()),
                        )
                    passage_vectors.append(vector)
                vectors.append(passage_vectors)
            return vectors

    def _read(self, row) -> list[float] | None:
        if row is None:
            return None
        payload, digest = row
        if not isinstance(payload, str) or hashlib.sha256(payload.encode()).hexdigest() != digest:
            return None
        try:
            vector = json.loads(payload)
            if not isinstance(vector, list) or len(vector) != self.embedding.dimension:
                return None
            if not all(type(value) in (int, float) and math.isfinite(value) for value in vector):
                return None
            norm = sum(value * value for value in vector)
            if norm != 0 and not math.isclose(norm, 1.0, abs_tol=1e-8):
                return None
            return vector
        except (TypeError, ValueError, OverflowError):
            return None
