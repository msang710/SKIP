"""Optional host-owned, session-only document cache; never an authority store."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any, Callable


CACHE_SCHEMA = "document-cache/v1"
MAX_CACHE_BYTES = 2_000_000
ARTIFACT_FIELDS = {"path", "kind", "status", "title", "project_id", "source_revision",
                   "review_verdict", "implementation_gate", "metadata_source", "input_chars", "input_bytes"}
SEMANTIC_FIELDS = {"goal", "facts", "confirmed_decisions", "requirements", "design", "tasks",
                   "human_review", "open_items"}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class SessionContext:
    """Supplied by a host adapter, not parsed from an agent request or environment."""

    cache_directory: Path
    session_id: str
    cleanup_on_session_end: bool


def valid_fragments(value: Any, relative: str) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    artifact, semantic = value
    if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_FIELDS:
        return False
    if artifact["path"] != relative or not isinstance(artifact["kind"], str):
        return False
    for key in ARTIFACT_FIELDS - {"input_chars", "input_bytes"}:
        if artifact[key] is not None and not isinstance(artifact[key], str):
            return False
    for key in ("input_chars", "input_bytes"):
        if type(artifact[key]) is not int or artifact[key] < 0:
            return False
    return (isinstance(semantic, dict) and set(semantic) == SEMANTIC_FIELDS and
            all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in semantic.values()))


class DocumentCache:
    def __init__(self, session: SessionContext | None, scope: dict[str, Any]) -> None:
        self.session = session
        self.scope = fingerprint({"schema": CACHE_SCHEMA, "scope": scope,
                                  "session": session.session_id if session else None})
        self.hits = 0
        self.parsed = 0
        self.warnings: list[str] = []
        self.enabled = bool(session and session.cleanup_on_session_end and session.session_id)
        if self.enabled:
            try:
                fd = self._open_root()
                os.close(fd)
            except (OSError, ValueError):
                self.enabled = False
                self.warnings.append("CACHE_UNAVAILABLE")

    def _open_root(self) -> int:
        assert self.session is not None
        root = Path(os.path.abspath(self.session.cache_directory))
        if root.resolve() != root:
            raise ValueError("cache root must not traverse symlinks")
        # Host creates and owns the directory and guarantees its removal.
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            os.close(fd)
            raise ValueError("cache root must be private and owned by the current user")
        return fd

    def load_document_cache(self, name: str, relative: str) -> list[Any] | None:
        fd = self._open_root()
        try:
            try:
                file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            except FileNotFoundError:
                return None
            with os.fdopen(file_fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                        stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_CACHE_BYTES):
                    raise ValueError("invalid cache file")
                record = json.loads(stream.read(MAX_CACHE_BYTES + 1))
            if (not isinstance(record, dict) or set(record) != {"schema", "key", "fragments"} or
                    record["schema"] != CACHE_SCHEMA or record["key"] != name or
                    not valid_fragments(record["fragments"], relative)):
                raise ValueError("invalid cache schema")
            return record["fragments"]
        finally:
            os.close(fd)

    def save_document_cache(self, name: str, fragments: list[Any]) -> None:
        data = json.dumps({"schema": CACHE_SCHEMA, "key": name, "fragments": fragments},
                          ensure_ascii=False).encode()
        if len(data) > MAX_CACHE_BYTES:
            self.warnings.append("CACHE_ITEM_TOO_LARGE")
            return
        fd = self._open_root()
        temporary = "." + secrets.token_hex(16) + ".tmp"
        try:
            file_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              0o600, dir_fd=fd)
            with os.fdopen(file_fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=fd)
            except FileNotFoundError:
                pass
            os.close(fd)

    def read(self, path: Path, relative: str, parse: Callable[..., Any]) -> tuple[dict, dict]:
        # Always read original bytes. Missing/unreadable originals never fall back to cache.
        raw = path.read_bytes()
        name = fingerprint({"scope": self.scope, "path": relative,
                            "digest": hashlib.sha256(raw).hexdigest()}) + ".json"
        if self.enabled:
            try:
                cached = self.load_document_cache(name, relative)
                if cached is not None:
                    self.hits += 1
                    return tuple(cached)
            except (OSError, ValueError, TypeError):
                self.warnings.append("CACHE_READ_FAILED")
        fragments = parse(path, relative, text_value=raw.decode("utf-8"))
        self.parsed += 1
        if self.enabled:
            try:
                self.save_document_cache(name, list(fragments))
            except (OSError, ValueError, TypeError):
                self.warnings.append("CACHE_WRITE_FAILED")
        return fragments
