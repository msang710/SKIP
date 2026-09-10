"""Bounded host-owned Codex session provenance; no SKIP records are read here."""
import json
import re
from pathlib import Path
from skip_core.common import digest
from skip_core.errors import CoreError
class EntryError(CoreError):
    def __init__(self,message): super().__init__('USER_ACTION_REQUIRED',message)
MAX_TAIL=16*1024*1024

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
