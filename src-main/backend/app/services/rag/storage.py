"""Safe local storage for uploaded RAG source files."""

from __future__ import annotations

import hashlib
import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from app.services.rag.errors import (
    InvalidDocumentError,
    MaterialTooLargeError,
    UnsupportedMaterialTypeError,
)

SUPPORTED_UPLOAD_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".html": "text/html",
}
_CHUNK_SIZE = 64 * 1024
_MAX_ZIP_ENTRIES = 10_000
_MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
_MAX_ZIP_COMPRESSION_RATIO = 100


@dataclass(frozen=True, slots=True)
class StagedUpload:
    temporary_path: Path
    safe_extension: str
    mime_type: str
    content_hash: str
    file_size_bytes: int


class FileStorage(Protocol):
    def stage_upload(self, filename: str | None, source: BinaryIO) -> StagedUpload: ...

    def commit(self, staged: StagedUpload, material_id: str) -> str: ...

    def delete(self, storage_key: str | None) -> None: ...

    def open_read(self, storage_key: str) -> BinaryIO: ...


class LocalFileStorage:
    def __init__(self, upload_dir: str | Path, max_file_bytes: int) -> None:
        self.upload_dir = Path(upload_dir).resolve()
        self.staging_dir = self.upload_dir / ".staging"
        self.max_file_bytes = max_file_bytes

    def stage_upload(self, filename: str | None, source: BinaryIO) -> StagedUpload:
        extension = Path(filename or "").suffix.lower()
        mime_type = SUPPORTED_UPLOAD_TYPES.get(extension)
        if mime_type is None:
            raise UnsupportedMaterialTypeError()
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self.staging_dir / f"{uuid.uuid4().hex}.upload"
        digest = hashlib.sha256()
        file_size_bytes = 0
        try:
            with temporary_path.open("xb") as destination:
                while block := source.read(_CHUNK_SIZE):
                    file_size_bytes += len(block)
                    if file_size_bytes > self.max_file_bytes:
                        raise MaterialTooLargeError()
                    digest.update(block)
                    destination.write(block)
            self._validate_signature(temporary_path, extension)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return StagedUpload(
            temporary_path=temporary_path,
            safe_extension=extension,
            mime_type=mime_type,
            content_hash=f"sha256:{digest.hexdigest()}",
            file_size_bytes=file_size_bytes,
        )

    def commit(self, staged: StagedUpload, material_id: str) -> str:
        storage_key = f"{material_id}/source{staged.safe_extension}"
        destination = self._resolve_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged.temporary_path, destination)
        return storage_key

    def delete(self, storage_key: str | None) -> None:
        if not storage_key:
            return
        target = self._resolve_key(storage_key)
        target.unlink(missing_ok=True)
        parent = target.parent
        if parent != self.upload_dir:
            try:
                parent.rmdir()
            except OSError:
                pass

    def open_read(self, storage_key: str) -> BinaryIO:
        return self._resolve_key(storage_key).open("rb")

    def _resolve_key(self, storage_key: str) -> Path:
        candidate = (self.upload_dir / storage_key).resolve()
        if candidate == self.upload_dir or self.upload_dir not in candidate.parents:
            raise ValueError("storage key escapes upload directory")
        return candidate

    @staticmethod
    def _validate_signature(path: Path, extension: str) -> None:
        with path.open("rb") as source:
            prefix = source.read(8)
        if extension == ".html":
            return
        if extension == ".pdf":
            if not prefix.startswith(b"%PDF-"):
                raise InvalidDocumentError()
            return
        if not prefix.startswith(b"PK\x03\x04"):
            raise InvalidDocumentError()
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > _MAX_ZIP_ENTRIES:
                    raise InvalidDocumentError()
                total_size = sum(entry.file_size for entry in entries)
                compressed_size = sum(entry.compress_size for entry in entries)
                if total_size > _MAX_ZIP_UNCOMPRESSED_BYTES:
                    raise InvalidDocumentError()
                if total_size and (compressed_size == 0 or total_size / compressed_size > _MAX_ZIP_COMPRESSION_RATIO):
                    raise InvalidDocumentError()
                names = set(archive.namelist())
        except zipfile.BadZipFile as error:
            raise InvalidDocumentError() from error
        required = {"[Content_Types].xml", "word/" if extension == ".docx" else "ppt/"}
        if "[Content_Types].xml" not in names or not any(
            name.startswith(next(iter(required - {"[Content_Types].xml"}))) for name in names
        ):
            raise InvalidDocumentError()
