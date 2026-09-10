"""Execution-host contract. Adapters, never request JSON, supply user provenance.

This is an advisory integration boundary, not isolation from a process that can
modify SKIP or impersonate its host. No OS write interception is provided.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os


class EntryError(ValueError):
    error_code = "invalid_entry"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def text(value, label, limit=8192):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise EntryError(f"invalid {label}")
    return value


def beneath(root: Path, relative: str) -> Path:
    # Reject Windows spellings on POSIX too: portable inputs have one meaning.
    from pathlib import PureWindowsPath
    text(relative, "relative path", 4096)
    path = Path(relative)
    windows = PureWindowsPath(relative)
    if path.is_absolute() or windows.drive or "\\" in relative or ".." in path.parts:
        raise EntryError("path must be relative and contained")
    resolved = (root.resolve() / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise EntryError("path escapes root")
    return resolved


@dataclass(frozen=True)
class HostContext:
    host_id: str
    execution_id: str
    session_id: str
    workspace: Path

    @classmethod
    def local(cls, workspace, *, host_id="cli", execution_id="local", session_id="read-only"):
        root = Path(workspace).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise EntryError("workspace must be a directory")
        if os.name == "nt" and str(root).startswith("\\\\"):
            raise EntryError("network workspace paths are not yet supported")
        for label, value in (("host", host_id), ("execution", execution_id), ("session", session_id)):
            text(value, label, 200)
        return cls(host_id, execution_id, session_id, root)

    def binding(self):
        return {"host_id": self.host_id, "execution_id": self.execution_id,
                "session_id": self.session_id, "workspace": os.path.normcase(str(self.workspace))}


@dataclass(frozen=True)
class UserEvent:
    """Host-adapter assertion of an actual action; not deserializable from work JSON.

    A native adapter must obtain text/id from its current user action, not an
    agent-authored envelope. Local CLI fallback obtains them interactively.
    """
    host_binding: str
    request_id: str
    request_digest: str
    operation: str
    origin: str

    @classmethod
    def from_native_action(cls, host, request_id, request_text, operation):
        text(request_id, "request id", 200)
        text(request_text, "user request")
        if not isinstance(operation, str) or operation not in {"activate", "answer", "plan", "implement", "validate"}:
            raise EntryError("unsupported user operation")
        return cls(digest(host.binding()), request_id, digest(request_text), operation, "native_user_action")

    def matches(self, host, request):
        return (self.host_binding == digest(host.binding()) and
                self.request_id == request.get("request_id") and
                self.request_digest == digest(request.get("text")) and
                self.operation == request.get("operation"))
