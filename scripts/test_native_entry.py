import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest
from scripts import test_workflow_entry as fixtures
from scripts.native_entry import dispatch


class NativeBridgeJourney(unittest.TestCase):
    setUp = fixtures.EntryJourney.setUp
    activate = fixtures.EntryJourney.activate
    request = fixtures.EntryJourney.request

    def test_native_stdin_uses_same_core_as_direct_calls(self):
        env = {'INTENT_TO_CODE_RECORD_ROOT': str(self.root), 'INTENT_TO_CODE_WORKSPACE_REGISTRY': str(self.registry)}
        base = {'host': {**self.host.binding(), 'workspace': str(self.workspace)}}
        with patch.dict('os.environ', env):
            result = dispatch({**base, 'command': 'activate', 'user_event': {'id': 'a', 'text': 'activate', 'operation': 'activate'}})
            self.assertEqual(result['status'], 'applied')
            request = self.request()
            event = {'id': request['request_id'], 'text': request['text'], 'operation': 'implement'}
            result = dispatch({**base, 'command': 'prepare', 'request': request, 'user_event': event})
            self.assertEqual(result['authorization']['status'], 'ALLOW')
            event['text'] = 'a different actual request'
            self.assertEqual(dispatch({**base, 'command': 'prepare', 'request': request, 'user_event': event})['status'], 'no_match')

    def test_recovery_after_registry_commit(self):
        def stop(stage):
            if stage == 'registry-written':
                raise RuntimeError('crash')
        with self.assertRaises(RuntimeError):
            self.activate(fault=stop)
        self.assertEqual(self.activate()['status'], 'applied')

    def test_native_errors_are_single_json(self):
        path = Path(__file__).with_name('native_entry.py')
        result = subprocess.run([sys.executable, str(path)], input='{}', text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['schema'], 'entry-error/v1')
