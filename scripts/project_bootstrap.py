"""Explicit activation transaction. Creates identity and measured NOW, never goals."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
if not __package__:
    import intent_context as context
    from host_context import EntryError, beneath, digest
    from goal_risk import snapshot
else:
    from scripts import intent_context as context
    from scripts.host_context import EntryError, beneath, digest
    from scripts.goal_risk import snapshot


def revision(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".skip-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


@contextmanager
def locked(path):
    """OS releases the lock on process exit; no stale PID deletion or daemon."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.seek(0, 2) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def preview(host, root, registry, *, paseo_project_id=None):
    root, registry = Path(root).resolve(), Path(registry).resolve()
    if root.is_relative_to(host.workspace) or registry.is_relative_to(host.workspace):
        raise EntryError("SKIP records and registry must be outside the product workspace")
    selected, warnings, method = context.project_from_registry(registry, host.workspace, paseo_project_id)
    if selected:
        project = beneath(root, f"projects/{selected}/project.yaml")
        if not project.is_file() or context.scalar_yaml(project).get("project_id") != selected:
            raise EntryError("registered project metadata is missing or inconsistent")
    identity = digest({"workspace": os.path.normcase(str(host.workspace)), "execution": host.execution_id})
    project_id = selected or "local-" + identity[:24]
    return {"schema": "bootstrap-preview/v1", "status": "resolved" if selected else "preview",
            "project_id": project_id, "identity": identity, "host": host.binding(),
            "record_root": str(root), "registry": str(registry), "registry_revision": revision(registry),
            "paseo_project_id": paseo_project_id, "resolution_method": method,
            "warnings": warnings, "creates_goals": False}


def apply(host, event, proposed, *, observations=(), fault=None):
    activation = {"request_id": event.request_id if event else None, "text": "activate", "operation": "activate"}
    if not event or not event.matches(host, activation):
        raise EntryError("activation requires a current native activation event")
    root, registry = Path(proposed["record_root"]), Path(proposed["registry"])
    if proposed["host"] != host.binding():
        raise EntryError("activation host changed")
    control = beneath(root, ".control/bootstrap")
    # Serialize registry and record changes across all projects of this registry.
    with locked(registry.with_name(registry.name + ".skip-lock")):
        journal_path = beneath(control, proposed["identity"] + ".json")
        journal = json.loads(journal_path.read_text()) if journal_path.is_file() else None
        if journal and journal["state"] != "complete":
            original = journal["preview"]
            if any(original[key] != proposed[key] for key in
                   ("identity", "host", "record_root", "registry", "project_id", "paseo_project_id")):
                raise EntryError("pending bootstrap requires its original preview")
            return _commit(journal_path, journal, fault)
        current = preview(host, root, registry, paseo_project_id=proposed["paseo_project_id"])
        if current["status"] == "resolved":
            if current["project_id"] != proposed["project_id"]:
                raise EntryError("project binding conflict")
            return {**current, "status": "applied", "changed": False}
        if current != proposed:
            raise EntryError("bootstrap preview is stale; inspect the current binding")
        project = beneath(root, "projects/" + proposed["project_id"])
        if project.exists():
            raise EntryError("unregistered project exists; refusing to overwrite it")
        registry_value = context.scalar_yaml(registry)
        if not registry_value:
            registry_value = {"version": 2, "projects": {}}
        projects = registry_value.setdefault("projects", {})
        context.registry_projects(registry_value)
        projects[proposed["project_id"]] = {"source_workspace": str(host.workspace)}
        if proposed["paseo_project_id"]:
            context.runtime_id(proposed["paseo_project_id"], "Paseo project")
            registry_value.setdefault("bindings", {}).setdefault("paseo", {})[proposed["paseo_project_id"]] = proposed["project_id"]
        metadata = {"version": 2, "project_id": proposed["project_id"], "display_name": host.workspace.name,
                    "workspace": {"source_root": "."}, "sources": {"workspace": {"kind": "directory", "source_root": "."}}}
        source = snapshot(host.workspace, list(observations))
        # NOW says only what this operation measured; no project purpose inferred.
        now = None
        if source["files"]:
            import datetime
            now = ("---\nkind: now\nproject_id: " + proposed["project_id"] +
                   "\nscope: system\nstatus: partially-verified\nverified_revision: unversioned\nverified_at: " +
                   datetime.date.today().isoformat() + "\nsource_id: workspace\nsource_root: .\n---\n\n")
            now += "# 현재 확인 범위\n\n파일 존재와 내용 해시를 확인했습니다. 업무 의미와 실행 동작은 검증하지 않았습니다.\n\n"
            now += "```json\n" + json.dumps(source, ensure_ascii=False, indent=2) + "\n```\n"
        journal = {"state": "prepared", "preview": proposed, "metadata": metadata,
                   "now": now, "registry_after": registry_value}
        atomic_write(journal_path, encoded(journal))
        return _commit(journal_path, journal, fault)


def _commit(journal_path, journal, fault=None):
    proposed = journal["preview"]
    root, registry = Path(proposed["record_root"]), Path(proposed["registry"])
    project = beneath(root, "projects/" + proposed["project_id"])
    after = encoded(journal["registry_after"])
    import hashlib
    after_digest = hashlib.sha256(after).hexdigest()
    if revision(registry) not in {proposed["registry_revision"], after_digest}:
        raise EntryError("registry changed during bootstrap; recovery left user files untouched")
    values = {"project.yaml": encoded(journal["metadata"])}
    if journal["now"]:
        values["NOW/system.md"] = journal["now"].encode()
    project.mkdir(parents=True, exist_ok=True)
    marker = beneath(project, ".bootstrap-pending")
    atomic_write(marker, proposed["identity"].encode())
    for relative, value in values.items():
        path = beneath(project, relative)
        if path.exists() and path.read_bytes() != value:
            raise EntryError("bootstrap-created file changed; refusing to overwrite it")
        if not path.exists():
            atomic_write(path, value)
    if fault:
        fault("project-written")
    if revision(registry) != after_digest:
        atomic_write(registry, after)
    if fault:
        fault("registry-written")
    marker.unlink(missing_ok=True)
    journal["state"] = "complete"
    atomic_write(journal_path, encoded(journal))
    return {**proposed, "status": "applied", "changed": True}
