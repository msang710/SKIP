"""Ephemeral authority objects. Never deserialize one from a model command."""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import hashlib
import secrets
import time
from .common import digest, uid
from .errors import require


@dataclass(frozen=True)
class Principal:
    project_id: str
    origin: str
    kind: str = 'agent'
    method: str | None = None
    verifier: str = 'model-tool'
    event_key: str = ''
    user_text: str = ''
    installation_admin: bool = False

    @property
    def fingerprint(self):
        return digest({'origin': self.origin, 'kind': self.kind, 'project': self.project_id})

    def human(self):
        require(self.kind == 'human' and self.method in ('native_user_action', 'host_user_turn', 'interactive_tty')
                and self.event_key and self.user_text, 'USER_ACTION_REQUIRED', 'A verified current user action is required')


@dataclass
class ExecutionContext:
    """Created by a host adapter after verification, not from model-visible input."""
    project_id: str
    sources: dict[str, Path]
    identity: tuple[str, ...]
    verify: object  # callable re-reads the host's current connection/target
    can_start: bool = False
    can_continue: bool = False
    context_id: str = field(default_factory=uid)
    generation: int = 1
    expires_at: float = field(default_factory=lambda: time.monotonic() + 1800)
    revoked: bool = False
    caller_verified: bool = False
    renewable_source: bool = False
    _tickets: dict = field(default_factory=dict, repr=False)

    @property
    def fingerprint(self):
        # Opaque receipt; it contains no recoverable endpoint, path or thread ID.
        return digest({'context': self.context_id, 'generation': self.generation})

    def check(self, *, start=False):
        require(not self.revoked and time.monotonic() < self.expires_at,
                'CONTEXT_EXPIRED', 'Current connection expired; reconnect here')
        require(tuple(self.verify()) == self.identity, 'STALE', 'Current environment changed')
        if start:
            require(self.can_start, 'TARGET_UNAVAILABLE', 'This host cannot verify the current execution target')

    def refresh_source(self):
        # Renewal is for source-only connections, never native execution rights.
        require(self.renewable_source and not self.can_start and not self.can_continue
                and not self.revoked, 'CONTEXT_EXPIRED', 'Source connection cannot be renewed')
        require(tuple(self.verify()) == self.identity, 'STALE', 'Current source changed')
        if time.monotonic() >= self.expires_at:
            self.generation += 1
            self._tickets.clear()
            self.expires_at = time.monotonic() + 1800

    def issue(self, payload):
        self.check()
        require(len(self._tickets) < 128, 'CONFLICT', 'Too many pending actions')
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (digest(payload), self.fingerprint, time.monotonic() + 300)
        return ticket

    def consume(self, ticket, payload, principal):
        principal.human()
        self.check()
        require(principal.origin == self.context_id and principal.project_id == self.project_id,
                'PROJECT_MISMATCH', 'User action belongs to another connection')
        value = self._tickets.pop(ticket, None)
        require(value is not None and value[0] == digest(payload) and value[1] == self.fingerprint
                and value[2] > time.monotonic(), 'STALE', 'Decision action expired or changed')

    def close(self):
        self.revoked = True
        self.generation += 1
        self._tickets.clear()


def relative_path(value):
    require(isinstance(value, str) and len(value) <= 1024 and '\\' not in value and ':' not in value
            and '\x00' not in value, 'INVALID_INPUT', 'Invalid source-relative path')
    p = PurePosixPath(value)
    require(value and not p.is_absolute() and '..' not in p.parts and str(p) == value,
            'INVALID_INPUT', 'Path must be normalized and source-relative')
    return value


def snapshot(context, paths):
    context.check()
    require(isinstance(paths, list) and 0 < len(paths) <= 128, 'INVALID_INPUT', 'A bounded source scope is required')
    entries = []
    total = 0
    for entry in paths:
        require(set(entry) == {'source_id', 'relative_path', 'access'}, 'INVALID_INPUT', 'Invalid scope path fields')
        source = entry['source_id']
        require(source in context.sources, 'PROJECT_MISMATCH', 'Source unavailable in this connection')
        require(entry['access'] in ('read', 'modify', 'create', 'delete'), 'INVALID_INPUT', 'Invalid access')
        rel = relative_path(entry['relative_path'])
        root = context.sources[source].resolve(strict=True)
        path = root / rel
        require(path.resolve().is_relative_to(root) and not path.is_symlink(), 'INVALID_INPUT', 'Source path escape')
        if not path.exists():
            value = None
        else:
            files = []
            if path.is_dir():
                import os
                for directory, dirs, names in os.walk(path, followlinks=False):
                    dirs[:] = [d for d in dirs if d != '.git']
                    require(not any((Path(directory)/d).is_symlink() for d in dirs), 'INVALID_INPUT', 'Symlink in source scope')
                    files.extend(Path(directory)/name for name in names)
                    require(len(files) <= 4096, 'INVALID_INPUT', 'Scope too large; narrow it before execution')
            else:
                files = [path]
            files.sort()
            hashes = []
            for file in files:
                if '.git' in file.relative_to(root).parts:
                    continue
                require(not file.is_symlink(), 'INVALID_INPUT', 'Symlink in source scope')
                if file.is_dir():
                    continue
                require(file.is_file() and file.resolve().is_relative_to(root), 'INVALID_INPUT', 'Unsupported source file')
                before = file.stat()
                total += before.st_size
                require(total <= 128 * 1024 * 1024, 'INVALID_INPUT', 'Scope exceeds snapshot budget')
                h = hashlib.sha256()
                with file.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(65536), b''):
                        h.update(chunk)
                after = file.stat()
                require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                        (after.st_ino, after.st_size, after.st_mtime_ns), 'STALE', 'Source changed while reading')
                hashes.append((file.relative_to(root).as_posix(), h.hexdigest()))
            value = digest(hashes)
        entries.append({'source_id': source, 'relative_path': rel, 'file_state': 'absent' if value is None else 'present',
                        'content_digest': value, 'source_revision': None})
    context.check()
    entries.sort(key=lambda x: (x['source_id'], x['relative_path']))
    require(len({(x['source_id'], x['relative_path']) for x in entries}) == len(entries), 'INVALID_INPUT', 'Duplicate scope')
    return {'digest': digest(entries), 'entries': entries}
