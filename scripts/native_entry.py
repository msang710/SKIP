"""Internal stdio bridge for a trusted native adapter.

Unlike `entry --request-file`, callers of this module own user-event provenance.
Paseo constructs the event from its native request form and keeps it in server
memory; subsequent agent risk inputs cannot change that event. This bridge does
not authenticate a process with the same filesystem privileges as its host.
"""
import json
import os
from pathlib import Path
import sys
if not __package__:
    import intent_context as context
    from host_context import HostContext, UserEvent, EntryError
    from project_bootstrap import preview, apply
    from workflow_entry import prepare, record_current
else:
    from scripts import intent_context as context
    from scripts.host_context import HostContext, UserEvent, EntryError
    from scripts.project_bootstrap import preview, apply
    from scripts.workflow_entry import prepare, record_current


def dispatch(value):
    host_data = value['host']
    host = HostContext.local(host_data['workspace'], host_id=host_data['host_id'],
                             execution_id=host_data['execution_id'], session_id=host_data['session_id'])
    root = Path(os.environ.get('INTENT_TO_CODE_RECORD_ROOT') or context.platform_data_root())
    registry = Path(os.environ.get('INTENT_TO_CODE_WORKSPACE_REGISTRY') or context.platform_registry())
    event_data = value.get('user_event')
    event = (UserEvent.from_native_action(host, event_data['id'], event_data['text'], event_data['operation'])
             if event_data else None)
    paseo_id = value.get('paseo_project_id')
    if value['command'] == 'activate':
        return apply(host, event, preview(host, root, registry, paseo_project_id=paseo_id),
                     observations=value.get('observations', []))
    if value['command'] == 'prepare':
        return prepare(host, root, registry, value.get('request'), event=event,
                       paseo_project_id=paseo_id, receipt=value.get('receipt'))
    if value['command'] == 'report':
        if not __package__:
            from workflow_report import validate_result, result_status_view
            from goal_risk import snapshot
        else:
            from scripts.workflow_report import validate_result, result_status_view
            from scripts.goal_risk import snapshot
        request = value['request']
        if not event or not event.matches(host, request):
            raise EntryError('current request origin unavailable')
        result = validate_result(value['result'])
        if result['requested_outcome'] != request['text']:
            raise EntryError('result belongs to another request')
        current = snapshot(host.workspace, request['scope']['paths'])
        if value['source_snapshot'] != current:
            raise EntryError('reported source changed; revalidate before presenting completion')
        plan = prepare(host, root, registry, request, event=event, paseo_project_id=paseo_id)
        goal = plan.get('goal', {})
        if goal.get('status') != 'resolved' or goal.get('lifecycle') != 'active' or goal.get('hold'):
            raise EntryError('result goal is unavailable')
        recorded = None
        if value.get('write_now'):
            recorded = record_current(host, root, plan['project_id'], goal['goal'], current,
                                      result['changes'], result['evidence'], expected_revision=value.get('expected_revision'), source_id=value.get('source_id'))
        return {'schema': 'workflow-plan/v2', 'status': 'prepared', 'goal': goal, 'result': result,
                'source_snapshot': current, 'recorded': recorded,
                'next_action': 'done' if result['outcome_status'] == 'complete' else 'verify',
                'view': result_status_view(result, goal['goal'])}
    if value['command'] == 'record-current':
        request = value['request']
        if not event or not event.matches(host, request):
            raise EntryError('current request origin unavailable')
        # Re-resolve the actual workspace, never accept a client-selected project.
        binding = preview(host, root, registry, paseo_project_id=paseo_id)
        if binding['status'] != 'resolved':
            raise EntryError('project is not active')
        current_plan = prepare(host, root, registry, request, event=event, paseo_project_id=paseo_id)
        goal = current_plan.get('goal', {})
        if goal.get('status') != 'resolved' or goal.get('lifecycle') != 'active' or goal.get('hold'):
            raise EntryError('goal is not active')
        return record_current(host, root, binding['project_id'], goal['goal'], value['source_snapshot'],
                              value['facts'], value['checks'], expected_revision=value.get('expected_revision'), source_id=value.get('source_id'))
    raise EntryError('unsupported native command')


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        value = json.loads(sys.stdin.read(2 * 1024 * 1024))
        result = dispatch(value)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'schema': 'entry-error/v1', 'status': 'error', 'error': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
