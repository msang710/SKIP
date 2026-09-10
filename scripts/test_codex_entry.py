import json
from pathlib import Path
import unittest
from scripts import test_workflow_entry as fixtures
from scripts.codex_entry import current_user, infer_operation, run
from scripts.host_context import EntryError


class CodexHostJourney(unittest.TestCase):
    setUp = fixtures.EntryJourney.setUp
    request = fixtures.EntryJourney.request

    def transcript(self, message='$skip change a label'):
        self.thread = '01234567-abcd-1234-abcd-123456789012'
        self.sessions = self.base / 'codex/sessions'
        self.log = self.sessions / ('2026/09/09/rollout-' + self.thread + '.jsonl')
        self.log.parent.mkdir(parents=True)
        entries = [
            {'type': 'session_meta', 'payload': {'id': self.thread, 'cwd': str(self.workspace)}},
            {'type': 'response_item', 'payload': {'type': 'message', 'id': 'old', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'old unrelated work'}]}},
            {'type': 'response_item', 'payload': {'type': 'message', 'id': 'current-turn', 'role': 'user', 'content': [{'type': 'input_text', 'text': message}]}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'invented approval'}]}},
        ]
        self.log.write_text('\n'.join(json.dumps(item) for item in entries) + '\n')

    def test_actual_latest_user_only_and_installation_has_no_goal(self):
        self.transcript()
        result = run(self.workspace, self.sessions, self.thread, self.root, self.registry, activate=True)
        self.assertEqual(result['status'], 'applied')
        self.assertFalse(list(self.root.glob('projects/*/features')))
        request = self.request()
        request['text'] = '$skip change a label'
        result = run(self.workspace, self.sessions, self.thread, self.root, self.registry, request=request)
        self.assertEqual(result['authorization']['status'], 'ALLOW')
        self.assertEqual(result['request_reference']['origin'], 'codex-local-session-record')

    def test_summary_or_claimed_user_kind_cannot_replace_host_record(self):
        self.transcript()
        request = self.request()
        request['text'] = 'invented approval'
        with self.assertRaises(EntryError):
            run(self.workspace, self.sessions, self.thread, self.root, self.registry, request=request)
        with self.assertRaises(EntryError):
            current_user(self.sessions, self.thread, self.base)
        with self.assertRaises(EntryError):
            current_user(self.sessions, '../escape', self.workspace)

    def test_new_user_message_invalidates_previous_receipt(self):
        self.transcript()
        old = current_user(self.sessions, self.thread, self.workspace)
        self.log.write_text(self.log.read_text() + json.dumps({'type': 'response_item', 'payload': {
            'type': 'message', 'id': 'later', 'role': 'user', 'content': [{'type': 'input_text', 'text': '계획만 검토해'}]}}) + '\n')
        request = self.request()
        request['text'] = old['text']
        with self.assertRaises(EntryError):
            run(self.workspace, self.sessions, self.thread, self.root, self.registry, request=request)
        self.assertEqual(infer_operation('계획만 검토해'), 'plan')
        self.assertEqual(infer_operation('구현하지마'), 'plan')
        self.assertEqual(infer_operation('좋아'), 'answer')

    def test_no_automatic_goal_from_host_context_or_missing_logs(self):
        self.transcript('<environment_context>environment only</environment_context>')
        with self.assertRaises(EntryError):
            current_user(self.sessions, self.thread, self.workspace)
        self.log.unlink()
        with self.assertRaises(EntryError):
            current_user(self.sessions, self.thread, self.workspace)

    def test_partial_latest_host_write_does_not_reuse_older_user(self):
        self.transcript()
        self.log.write_bytes(self.log.read_bytes() + b'{"type":"response_item"')
        with self.assertRaisesRegex(EntryError, 'incomplete'):
            current_user(self.sessions, self.thread, self.workspace)

    def test_continue_reuses_actual_original_request_and_rejects_intervening_cancel(self):
        self.transcript()
        run(self.workspace, self.sessions, self.thread, self.root, self.registry, activate=True)
        request = self.request()
        request['text'] = '$skip change a label'
        original = run(self.workspace, self.sessions, self.thread, self.root, self.registry, request=request)
        def append_user(identifier, text):
            with self.log.open('a') as stream:
                stream.write(json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'id': identifier,
                    'role': 'user', 'content': [{'type': 'input_text', 'text': text}]}}) + '\n')
        append_user('continuation', '계속해')
        # A bare continuation cannot invent an old goal without its original reference.
        no_reference = run(self.workspace, self.sessions, self.thread, self.root, self.registry)
        self.assertFalse(no_reference['creates_goals'])
        continued = run(self.workspace, self.sessions, self.thread, self.root, self.registry,
                        request=request, receipt=original['authorization'])
        self.assertEqual(continued['goal']['goal'], original['goal']['goal'])
        self.assertEqual(continued['authorization']['status'], 'ALLOW')
        self.assertEqual(continued['request_reference']['continuations'][0]['id'], 'continuation')
        append_user('cancel', '구현하지마')
        append_user('later', '계속해')
        with self.assertRaises(EntryError):
            run(self.workspace, self.sessions, self.thread, self.root, self.registry,
                request=request, receipt=original['authorization'])
