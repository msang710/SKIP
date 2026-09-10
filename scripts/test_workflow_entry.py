"""Behavioral tests shared by embedded Windows and Linux Core."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from scripts.host_context import EntryError, HostContext, UserEvent, digest
from scripts.project_bootstrap import preview, apply
from scripts.goal_risk import snapshot, POLICY_VERSION
from scripts.workflow_entry import prepare, record_current
from scripts import intent_context as context


class EntryJourney(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / '한글 workspace'
        self.workspace.mkdir()
        (self.workspace / 'app.txt').write_text('old', encoding='utf-8')
        self.root, self.registry = self.base / 'records', self.base / 'config' / 'registry.yaml'
        self.host = HostContext.local(self.workspace, host_id='native-test', session_id='one')

    def activate(self, **kw):
        event = UserEvent.from_native_action(self.host, 'activation', 'activate', 'activate')
        return apply(self.host, event, preview(self.host, self.root, self.registry), **kw)

    def request(self):
        scope = {'paths': ['app.txt'], 'summary': 'change a label'}
        goal = {'schema': 'goal-risk/v1', 'revision': 1, 'affects': [], 'failure_impact': 'cosmetic',
                'reversibility': 'easy', 'uncertainty': 'low', 'evidence': ['app.txt']}
        change = {'schema': 'change-risk/v1', 'goal_revision': 1, 'source_digest': snapshot(self.workspace, scope['paths'])['digest'],
                  'scope_digest': digest(scope), 'policy_version': POLICY_VERSION, 'affects': [],
                  'reversibility': 'easy', 'uncertainty': 'low', 'evidence': ['app.txt'], 'exclusions': {}}
        return {'schema': 'workflow-request/v2', 'request_id': 'current-turn', 'text': 'change a label', 'operation': 'implement',
                'scope': scope, 'open_decisions': [], 'goal_risk': goal, 'change_risk': change}

    def run_request(self, request, **kw):
        event = UserEvent.from_native_action(self.host, request['request_id'], request['text'], request['operation'])
        return prepare(self.host, self.root, self.registry, request, event=event, **kw)

    def test_install_read_only_and_activation_no_goal_or_empty_bundle(self):
        result = prepare(self.host, self.root, self.registry)
        self.assertEqual(result['next_action'], 'activate')
        self.assertFalse(self.root.exists())
        installed = self.activate()
        files = list((self.root / 'projects' / installed['project_id']).rglob('*'))
        self.assertEqual([p.name for p in files], ['project.yaml'])
        self.assertFalse(self.activate()['changed'])

    def test_observed_now_contains_only_current_measurements(self):
        installed = self.activate(observations=['app.txt'])
        project = self.root / 'projects' / installed['project_id']
        self.assertTrue((project / 'NOW/system.md').is_file())
        self.assertFalse((project / 'features').exists())
        self.assertFalse((project / 'NOW/goals').exists())

    def test_direct_small_request_needs_no_artifacts_or_repeat_approval(self):
        self.activate()
        request = self.request()
        result = self.run_request(request)
        self.assertEqual(result['policy']['workflow_depth'], 'compact')
        self.assertEqual(result['authorization']['status'], 'ALLOW')
        self.assertEqual(result['next_action'], 'implement')
        self.assertFalse(list(self.root.glob('projects/*/features')))
        self.assertEqual(self.run_request(request, receipt=result['authorization'])['authorization'], result['authorization'])

    def test_request_json_cannot_claim_authority(self):
        self.activate()
        request = self.request()
        self.assertEqual(prepare(self.host, self.root, self.registry, request)['status'], 'no_match')
        request['authority'] = {'kind': 'user_turn'}
        with self.assertRaises(EntryError):
            prepare(self.host, self.root, self.registry, request)

    def test_activation_does_not_authorize_implementation(self):
        self.activate()
        event = UserEvent.from_native_action(self.host, 'current-turn', 'activate', 'activate')
        result = prepare(self.host, self.root, self.registry, self.request(), event=event)
        self.assertEqual(result['status'], 'no_match')

    def test_host_or_session_change_invalidates_origin(self):
        self.activate()
        req = self.request()
        event = UserEvent.from_native_action(self.host, req['request_id'], req['text'], 'implement')
        host = HostContext.local(self.workspace, session_id='new')
        self.assertEqual(prepare(host, self.root, self.registry, req, event=event)['status'], 'no_match')

    def test_material_and_unknown_impacts(self):
        self.activate()
        for dimension in ('inventory', 'permissions', 'money', 'boot_recovery', 'sensitive_data'):
            request = self.request()
            request['change_risk']['affects'] = [dimension]
            result = self.run_request(request)
            self.assertEqual(result['policy']['workflow_depth'], 'full')
            self.assertEqual(result['authorization']['status'], 'BLOCKED')
        request = self.request()
        request['change_risk']['uncertainty'] = 'unknown'
        self.assertEqual(self.run_request(request)['next_action'], 'inspect_source')

    def test_goal_risk_cannot_be_silently_downgraded(self):
        self.activate()
        request = self.request()
        request['goal_risk']['affects'] = ['inventory']
        self.assertEqual(self.run_request(request)['policy']['workflow_depth'], 'full')
        request['change_risk']['exclusions'] = {'inventory': 'missing.txt'}
        self.assertEqual(self.run_request(request)['next_action'], 'inspect_source')
        request['change_risk']['exclusions'] = {'inventory': 'app.txt'}
        self.assertEqual(self.run_request(request)['policy']['workflow_depth'], 'compact')

    def test_stale_source_scope_and_policy_require_investigation(self):
        self.activate()
        original = self.request()
        for field in ('source_digest', 'scope_digest', 'policy_version', 'goal_revision'):
            request = deepcopy(original)
            request['change_risk'][field] = 'stale'
            self.assertEqual(self.run_request(request)['next_action'], 'inspect_source')
        receipt = self.run_request(original)['authorization']
        (self.workspace / 'app.txt').write_text('new')
        fresh = self.request()
        self.assertEqual(self.run_request(fresh, receipt=receipt)['authorization']['status'], 'STALE')
        fresh['scope']['summary'] = 'expanded scope'
        fresh['change_risk']['scope_digest'] = digest(fresh['scope'])
        denied = self.run_request(fresh, receipt=receipt)['authorization']
        self.assertEqual(denied['status'], 'BLOCKED')
        self.assertIn('REQUEST_SCOPE_CHANGED', denied['reasons'])


    def test_open_decisions_and_read_requests_cannot_implement(self):
        self.activate()
        request = self.request()
        request['open_decisions'] = ['D-1']
        self.assertEqual(self.run_request(request)['authorization']['status'], 'BLOCKED')
        request['open_decisions'] = []
        request['operation'] = 'plan'
        result = self.run_request(request)
        self.assertEqual(result['next_action'], 'present_plan')
        self.assertEqual(result['authorization']['status'], 'BLOCKED')

    def test_interrupted_bootstrap_recovers_without_duplicates(self):
        def stop(stage):
            raise RuntimeError(stage)
        with self.assertRaises(RuntimeError):
            self.activate(fault=stop)
        project = next((self.root / 'projects').iterdir())
        args = argparse.Namespace(project=project.name, record_root=str(self.root), registry=str(self.registry), workspace=str(self.workspace))
        with self.assertRaises(context.SelectionError):
            context.resolve_project(args)
        self.activate()
        self.assertEqual(len(list((self.root / 'projects').iterdir())), 1)
        self.assertFalse((project / '.bootstrap-pending').exists())

    def test_interrupted_bootstrap_never_overwrites_user_edits(self):
        def stop(stage):
            raise RuntimeError(stage)
        with self.assertRaises(RuntimeError):
            self.activate(fault=stop)
        project = next((self.root / 'projects').iterdir())
        (project / 'project.yaml').write_text('user changed metadata')
        with self.assertRaises(EntryError):
            self.activate()
        self.assertEqual((project / 'project.yaml').read_text(), 'user changed metadata')

    def test_now_compare_and_swap_and_stale_evidence(self):
        installed = self.activate()
        result = self.run_request(self.request())
        args = (self.host, self.root, installed['project_id'], result['goal']['goal'], result['source_snapshot'], ['현재 라벨 확인'], [])
        output = record_current(*args)
        self.assertTrue(Path(output['path']).exists())
        with self.assertRaises(EntryError):
            record_current(*args)
        (self.workspace / 'app.txt').write_text('later')
        with self.assertRaises(EntryError):
            record_current(*args, expected_revision=output['revision'])

    def test_no_git_or_python_on_path_required_for_core(self):
        with patch.dict(os.environ, {'PATH': ''}):
            self.activate()
            self.assertEqual(self.run_request(self.request())['next_action'], 'implement')

    def test_paths_cannot_escape_and_records_stay_external(self):
        for path in ('../outside', 'C:\\elsewhere', '/etc/passwd', 'dir\\file'):
            with self.assertRaises(EntryError):
                snapshot(self.workspace, [path])
        with self.assertRaises(EntryError):
            preview(self.host, self.workspace / 'records', self.registry)

    def test_cli_has_one_json_response_and_no_record_side_effect(self):
        command = [sys.executable, str(Path(context.__file__)), 'entry', '--workspace', str(self.workspace),
                   '--record-root', str(self.root), '--registry', str(self.registry)]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['schema'], 'workflow-plan/v2')
        self.assertFalse(self.root.exists())

    def test_existing_artifacts_and_revocation_cannot_use_compact_bypass(self):
        installed = self.activate()
        feature = self.root / 'projects' / installed['project_id'] / 'features' / 'existing'
        feature.mkdir(parents=True)
        path = feature / 'prd.md'
        path.write_text('---\nschema: skip-artifact/v1\nstatus: draft\ndecisions:\n  open: ["D-1"]\n---\n# Existing\n')
        request = self.request()
        request['goal'] = 'existing'
        result = self.run_request(request)
        self.assertEqual(result['policy']['workflow_depth'], 'full')
        self.assertEqual(result['authorization']['status'], 'BLOCKED')
        self.assertIn('OPEN_PRODUCT_DECISIONS', result['authorization']['reasons'])
        path.write_text('---\nstatus: revoked\n---\n# Existing\n')
        self.assertEqual(self.run_request(request)['next_action'], 'stop')

    def test_exact_slug_outranks_many_incidental_terms(self):
        installed = self.activate()
        from scripts.workflow_entry import identity_args
        args = identity_args(self.host, self.root, self.registry, installed['project_id'])
        args.query, args.stdin = 'label alpha beta gamma delta epsilon zeta', False
        candidates = [
            {'slug': 'label', 'title': None, 'summary': None, 'evidence': []},
            {'slug': 'unrelated', 'title': 'zeta epsilon delta gamma beta alpha', 'summary': None, 'evidence': []},
        ]
        with patch.object(context, 'goal_candidates', return_value=candidates):
            self.assertEqual(context.resolve_goal_query(args)['goal'], 'label')

    def test_self_contained_answer_never_requires_project_setup(self):
        request = self.request()
        request['operation'] = 'answer'
        with patch.object(context, 'project_from_registry', side_effect=AssertionError('must not access registry')):
            result = prepare(self.host, self.root, self.registry, request)
        self.assertEqual(result['next_action'], 'answer')
        self.assertFalse(self.root.exists())

    def test_malformed_operation_is_a_contract_error(self):
        request = self.request()
        request['operation'] = []
        with self.assertRaises(EntryError):
            prepare(self.host, self.root, self.registry, request)

    def test_bootstrap_lock_excludes_another_process(self):
        from scripts.project_bootstrap import locked
        lock = self.base / 'shared.lock'
        program = 'from scripts.project_bootstrap import locked; from pathlib import Path; import sys\nwith locked(Path(sys.argv[1])): print("acquired")'
        with locked(lock):
            result = subprocess.run([sys.executable, '-c', program, str(lock)], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('acquired', result.stdout)

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows path semantics')
    def test_windows_case_identity(self):
        other = HostContext.local(str(self.workspace).upper(), host_id=self.host.host_id, session_id=self.host.session_id)
        self.assertEqual(other.binding(), self.host.binding())

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows junctions')
    def test_windows_junction_escape(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'secret.txt').write_text('outside')
        junction = self.workspace / 'escape'
        subprocess.run([os.environ['COMSPEC'], '/c', 'mklink', '/J', str(junction), str(outside)],
                       check=True, capture_output=True)
        try:
            with self.assertRaises(EntryError):
                snapshot(self.workspace, ['escape/secret.txt'])
        finally:
            junction.rmdir()

    @unittest.skipUnless(os.name == 'nt', 'requires native Windows file sharing locks')
    def test_windows_locked_destination_preserves_original(self):
        from scripts.project_bootstrap import atomic_write
        target = self.base / 'locked.txt'
        target.write_bytes(b'original')
        with target.open('rb'):
            with self.assertRaises(PermissionError):
                atomic_write(target, b'replacement')
        self.assertEqual(target.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
