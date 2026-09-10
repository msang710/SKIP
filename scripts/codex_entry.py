"""Codex local-session adapter for the same Core used by Paseo.

Read only the selected live thread's newest actual user message. Never use a
conversation summary, an assistant message, or a request's claimed `kind` as
provenance. Session files are host-owned operational inputs, not an isolation
boundary against another process running as the same OS user. Unknown formats
fail closed. This adapter requires Codex's local session record capability.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
if not __package__:
    import intent_context as context
    from host_context import EntryError, HostContext, UserEvent, digest
    from workflow_entry import prepare
    from project_bootstrap import preview, apply
else:
    from scripts import intent_context as context
    from scripts.host_context import EntryError, HostContext, UserEvent, digest
    from scripts.workflow_entry import prepare
    from scripts.project_bootstrap import preview, apply

MAX_TAIL = 16 * 1024 * 1024


def is_continuation(value):
    value = re.sub(r'^[/$]skip\s+', '', value, flags=re.I)
    normalized = re.sub(r'[.!?。！？\s]+', '', value.casefold())
    return normalized in {'계속해', '계속해줘', '계속진행해', '진행해', '응', '좋아', '그래',
                          '어디까지했어', '어디까지됐어', '진행상황알려줘', 'status', 'continue', 'proceed', 'yes', 'ok', 'okay'}


def current_user(session_root, thread_id, workspace, *, request_id=None):
    if not re.fullmatch(r'[a-f0-9-]{16,64}', thread_id):
        raise EntryError('current Codex thread identity unavailable')
    matches = []
    for path in session_root.glob('*/*/*/*' + thread_id + '*.jsonl'):
        matches.append(path)
        if len(matches) > 1:
            break
    if len(matches) != 1:
        raise EntryError('current Codex session record missing or ambiguous')
    path = matches[0]
    if path.is_symlink() or not path.resolve().is_relative_to(session_root.resolve()):
        raise EntryError('Codex session record escapes its host root')
    with path.open('rb') as stream:
        meta = json.loads(stream.readline(256 * 1024))
        if meta.get('type') != 'session_meta':
            raise EntryError('unsupported Codex session metadata')
        metadata = meta['payload']
        if not isinstance(metadata, dict):
            raise EntryError('invalid Codex session metadata')
        if metadata.get('id') != thread_id or Path(metadata.get('cwd', '')).resolve() != workspace.resolve():
            raise EntryError('Codex session and execution workspace do not match')
        stream.seek(0, 2)
        size = stream.tell()
        start = max(0, size - MAX_TAIL)
        stream.seek(start)
        if start:
            stream.readline()  # discard partial JSON line
        tail = stream.read(MAX_TAIL)
        if tail and not tail.endswith(b'\n'):
            raise EntryError('Codex session write is incomplete; retry after it settles')
        lines = tail.splitlines()
    continuations = []
    for raw in reversed(lines):
        try:
            item = json.loads(raw)
        except ValueError as exc:
            raise EntryError('invalid Codex session event; cannot verify latest user origin') from exc
        if not isinstance(item, dict):
            raise EntryError('invalid Codex session event')
        payload = item.get('payload', {})
        if not isinstance(payload, dict):
            raise EntryError('invalid Codex session payload')
        if item.get('type') != 'response_item' or payload.get('type') != 'message' or payload.get('role') != 'user':
            continue
        content = payload.get('content')
        if not isinstance(content, list) or not all(isinstance(part, dict) and part.get('type') == 'input_text' for part in content):
            raise EntryError('current user message format requires native host confirmation')
        value = '\n'.join(part['text'] for part in content)
        if not payload.get('id') or not value.strip():
            raise EntryError('current user message has no stable reference')
        # Host context envelopes are not a new work request.
        if value.lstrip().startswith(('<environment_context>', '<recommended_plugins>', '<permissions')):
            raise EntryError('latest user-role item is host context, not a work request')
        if request_id is not None and payload['id'] != request_id:
            if not is_continuation(value):
                raise EntryError('a later user instruction changed or stopped the anchored request')
            continuations.append({'id': payload['id'], 'digest': digest(payload)})
            continue
        return {'id': payload['id'], 'text': value, 'source': str(path), 'digest': digest(payload),
                'continuations': continuations}
    raise EntryError('current user message unavailable in bounded session tail')


def infer_operation(value):
    """Conservative convenience route; domain intent remains the agent's responsibility."""
    if re.search(r'구현\s*하지|수정\s*하지|코드\s*변경\s*하지|do not (implement|edit)|don.t (implement|edit)', value, re.I):
        return 'plan'
    if re.search(r'계획|검토|분석|설계|\b(plan|review|analy[sz]e|design)\b', value, re.I):
        return 'plan'
    if re.search(r'구현\s*(해|하자|하세요|시작|진행)|고쳐|수정해|추가해|만들어|바꿔|(?:^|[/$]skip\s+)(?:please\s+|can you\s+)?(implement|fix|add|build|change)\b', value, re.I):
        return 'implement'
    return 'answer'


def run(workspace, session_root, thread_id, root, registry, *, request=None, activate=False, receipt=None):
    user = current_user(session_root, thread_id, workspace)
    host = HostContext.local(workspace, host_id='codex', execution_id='local', session_id=thread_id)
    if activate:
        if not re.search(r'(?<!\w)[/$]skip\b|\bSKIP\b', user['text'], re.I):
            raise EntryError('activation requires a current explicit SKIP invocation')
        event = UserEvent.from_native_action(host, user['id'], 'activate', 'activate')
        return apply(host, event, preview(host, root, registry))
    if request is not None and request.get('request_id') != user['id']:
        if not isinstance(receipt, dict) or receipt.get('schema') != 'execution-gate/v2':
            raise EntryError('continuation needs the original request receipt, not remembered scope')
        user = current_user(session_root, thread_id, workspace, request_id=request.get('request_id'))
    operation = infer_operation(user['text'])
    if request is None:
        request = {'schema': 'workflow-request/v2', 'request_id': user['id'], 'text': user['text'], 'operation': operation,
                   'scope': {'paths': [], 'summary': user['text']}, 'open_decisions': []}
    if request.get('text') != user['text'] or request.get('request_id') != user['id'] or request.get('operation') != operation:
        raise EntryError('request does not match the actual current Codex user message and operation')
    event = UserEvent.from_native_action(host, user['id'], user['text'], operation)
    result = prepare(host, root, registry, request, event=event, receipt=receipt)
    result['request_reference'] = {'request_id': user['id'], 'text': user['text'], 'operation': operation,
                                   'origin': 'codex-local-session-record', 'digest': user['digest'], 'continuations': user['continuations']}
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--request-file', type=Path)
    parser.add_argument('--receipt-file', type=Path)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    try:
        home = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
        result = run(args.workspace, home / 'sessions', os.environ.get('CODEX_THREAD_ID', ''),
                     Path(os.environ.get('INTENT_TO_CODE_RECORD_ROOT') or context.platform_data_root()),
                     Path(os.environ.get('INTENT_TO_CODE_WORKSPACE_REGISTRY') or context.platform_registry()),
                     request=json.loads(args.request_file.read_text(encoding='utf-8')) if args.request_file else None,
                     receipt=json.loads(args.receipt_file.read_text(encoding='utf-8')) if args.receipt_file else None,
                     activate=args.activate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'schema': 'entry-error/v1', 'status': 'error', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
