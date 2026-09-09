#!/usr/bin/env python3
"""Recoverable, goal-scoped storage for the SKIP decision runtime."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


MAX_EVENT_BYTES = 256_000


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError("RECOVERY_REQUIRED", f"invalid runtime record: {path}") from exc
    if not isinstance(value, dict):
        raise StoreError("RECOVERY_REQUIRED", f"runtime record is not an object: {path}")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    payload = canonical_bytes(value)
    if len(payload) > MAX_EVENT_BYTES:
        raise StoreError("INVALID_TRANSITION", "runtime record exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True)
class RuntimeStore:
    state_dir: Path

    @property
    def ledger_dir(self) -> Path:
        return self.state_dir / "ledger"

    @property
    def projection_path(self) -> Path:
        return self.state_dir / "projection.yaml"

    @property
    def transactions_dir(self) -> Path:
        return self.state_dir / "transactions"

    @property
    def lock_dir(self) -> Path:
        return self.state_dir / "lock"

    def initialize(self) -> None:
        if self.state_dir.is_symlink():
            raise StoreError("INVALID_TRANSITION", "runtime state cannot be a symlink")
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.transactions_dir.mkdir(parents=True, exist_ok=True)

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        self.initialize()
        try:
            self.lock_dir.mkdir()
        except FileExistsError as exc:
            raise StoreError("LEDGER_CONFLICT", "goal runtime is locked") from exc
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                self.lock_dir.rmdir()

    def events(self) -> list[dict[str, Any]]:
        if not self.ledger_dir.exists():
            return []
        paths = sorted(self.ledger_dir.glob("*.yaml"))
        events = [read_object(path) for path in paths]
        previous: str | None = None
        for expected, event in enumerate(events, start=1):
            if event.get("sequence") != expected or event.get("previous_event_id") != previous:
                raise StoreError("LEDGER_CONFLICT", "ledger sequence or hash chain is invalid")
            previous = str(event.get("event_id"))
        return events

    def commit(self, event: dict[str, Any], projection: dict[str, Any]) -> None:
        """Commit an immutable event, then its rebuildable projection cache."""
        self.initialize()
        sequence = int(event["sequence"])
        event_id = str(event["event_id"])
        event_path = self.ledger_dir / f"{sequence:08d}-{event_id}.yaml"
        if event_path.exists():
            if read_object(event_path) == event:
                atomic_write(self.projection_path, projection)
                return
            raise StoreError("LEDGER_CONFLICT", "event identity already exists with different content")
        payload = canonical_bytes(event)
        if len(payload) > MAX_EVENT_BYTES:
            raise StoreError("INVALID_TRANSITION", "ledger event exceeds size limit")
        try:
            with event_path.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise StoreError("LEDGER_CONFLICT", "event was committed concurrently") from exc
        atomic_write(self.projection_path, projection)

    def recover(self, projection: dict[str, Any]) -> None:
        """Projection is a cache: recovery always rebuilds it from committed events."""
        self.initialize()
        for transaction in self.transactions_dir.iterdir():
            if transaction.is_dir():
                shutil.rmtree(transaction)
            else:
                transaction.unlink()
        atomic_write(self.projection_path, projection)
