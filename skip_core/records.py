"""Typed aggregate registry. No table/column names come from caller SQL."""
from .common import digest, identifier, now, text, uid
from .errors import require

FIELDS = {
 'goal': ('title','intent','success_definition'),
 'decision': ('question','rationale','risk_summary'),
 'requirement': ('title','statement','rationale'),
 'plan': ('title','design_body','scope_description','alternatives_body','rollback_body'),
 'work_item': ('operation','title','instruction_body','completion_definition','workflow_depth','request_id'),
}
# public child key: (table, owner id column, owner revision column, exact payload columns)
CHILDREN = {
 'decision': {'options': ('decision_options','decision_id','decision_revision',
                          ('option_id','label','description','consequences','recommended','position'))},
 'requirement': {
  'criteria': ('acceptance_criteria','requirement_id','requirement_revision',('criterion_id','description','given_text','when_text','then_text','required')),
  'decisions': ('requirement_decisions','requirement_id','requirement_revision',('decision_id','decision_revision','rationale')),
  'selections': ('requirement_selections','requirement_id','requirement_revision',('selection_id','rationale'))},
 'plan': {
  'items': ('plan_items','plan_id','plan_revision',('item_id','title','design_body','verification_body','position')),
  'requirements': ('plan_requirements','plan_id','plan_revision',('requirement_id','requirement_revision','rationale')),
  'decisions': ('plan_decisions','plan_id','plan_revision',('decision_id','decision_revision','rationale')),
  'selections': ('plan_selections','plan_id','plan_revision',('selection_id','rationale'))},
 'work_item': {
  'checks': ('work_checks','work_item_id','work_revision',('check_id','description','surface','required')),
  'requirements': ('work_item_requirements','work_item_id','work_item_revision',('requirement_id','requirement_revision','rationale')),
  'plan_items': ('work_item_plan_items','work_item_id','work_revision',('plan_id','plan_revision','plan_item_id','rationale')),
  'dependencies': ('work_dependencies','work_item_id','work_revision',('depends_on_id','depends_on_revision','reason'))},
 'goal': {},
}


def insert(c, table, values):
    # This helper is only called with identifiers from the static registry/application.
    names = ','.join(values)
    c.execute(f'INSERT INTO {table} ({names}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))


def get(c, project, kind, ident, revision=None):
    require(kind in FIELDS, 'INVALID_INPUT', 'Unknown record kind')
    head = c.execute(f'SELECT * FROM {kind}s WHERE project_id=? AND id=?', (project, ident)).fetchone()
    require(head is not None, 'NOT_FOUND', 'Record unavailable')
    rev = revision if revision is not None else head['current_revision']
    row = c.execute(f'SELECT * FROM {kind}_versions WHERE project_id=? AND id=? AND revision=? AND sealed_at IS NOT NULL',
                    (project, ident, rev)).fetchone()
    require(row is not None, 'NOT_FOUND', 'Record version unavailable')
    children = {}
    for key, (table, owner, version, fields) in CHILDREN[kind].items():
        children[key] = [dict(r) for r in c.execute(
            f'SELECT {",".join(fields)} FROM {table} WHERE project_id=? AND {owner}=? AND {version}=?',
            (project, ident, rev))]
    origin = c.execute('SELECT document_id,source_key,source_status,source_date,classification,unresolved_json FROM record_origins WHERE project_id=? AND kind=? AND record_id=? AND revision=?',(project,kind,ident,rev)).fetchone()
    return {'origin': dict(origin) if origin else None, 'kind': kind, 'id': ident, 'revision': rev, 'current_revision': head['current_revision'],
            'goal_id': head['goal_id'] if kind != 'goal' else ident, 'lifecycle': head['lifecycle'],
            'digest': row['content_digest'], 'fields': {f: row[f] for f in FIELDS[kind]}, 'children': children}


def publish(c, project, payload, event, *, allow_new_goal=False, record_origin=None):
    kind = payload['kind']
    require(kind in FIELDS, 'INVALID_INPUT', 'Unknown record kind')
    ident = identifier(payload.get('id') or uid())
    old = c.execute(f'SELECT * FROM {kind}s WHERE project_id=? AND id=?', (project, ident)).fetchone()
    expected = payload['expected_revision']
    require(type(expected) is int and expected >= 0 and expected == (old['current_revision'] if old else 0),
            'STALE', 'Record version changed')
    require(old or kind != 'goal' or allow_new_goal, 'USER_ACTION_REQUIRED', 'Goals start with actual user requests')
    fields, children = payload['fields'], payload.get('children', {})
    require(set(fields) == set(FIELDS[kind]) and set(children) <= set(CHILDREN[kind]), 'INVALID_INPUT', 'Unexpected record fields')
    for value in fields.values():
        text(value)
    origin = payload['request_id']
    require(c.execute('SELECT 1 FROM requests WHERE project_id=? AND id=?', (project, origin)).fetchone(),
            'USER_ACTION_REQUIRED', 'An actual request is required')
    goal = payload.get('goal_id')
    if kind != 'goal':
        g = c.execute('SELECT lifecycle FROM goals WHERE project_id=? AND id=?', (project, goal)).fetchone()
        require(g and g['lifecycle'] == 'active', 'NOT_FOUND', 'Active goal required')
        require(not old or old['goal_id'] == goal, 'CONFLICT', 'Record goal cannot change')
    rev = expected + 1
    if not old:
        values = dict(project_id=project, id=ident, origin_request_id=origin, lifecycle='active', last_event_id=event, created_at=now())
        if kind != 'goal':
            values['goal_id'] = goal
        insert(c, kind+'s', values)
    insert(c, kind+'_versions', dict(project_id=project, id=ident, revision=rev, **fields, created_event_id=event, created_at=now()))
    for key, rows in children.items():
        require(isinstance(rows, list) and len(rows) <= 128, 'INVALID_INPUT', 'Too many record children')
        table, owner, version, columns = CHILDREN[kind][key]
        for row in rows:
            require(isinstance(row, dict) and set(row) == set(columns), 'INVALID_INPUT', 'Invalid record relationship')
            require(all(isinstance(v, (str,int)) and not isinstance(v, bool) and (not isinstance(v,str) or len(v)<=65536)
                        for v in row.values()), 'INVALID_INPUT', 'Invalid child value')
            insert(c, table, dict(project_id=project, **{owner:ident,version:rev}, **row))
    if record_origin is not None:
        insert(c, 'record_origins', dict(project_id=project,kind=kind,record_id=ident,revision=rev,**record_origin))
    # Hash all text and exact child links, independent of caller list ordering.
    canonical_children = {key: sorted(rows, key=lambda x: digest(x)) for key, rows in children.items()}
    c.execute(f'UPDATE {kind}_versions SET content_digest=?,sealed_at=? WHERE project_id=? AND id=? AND revision=?',
              (digest({'fields':fields,'children':canonical_children}),now(),project,ident,rev))
    return ident, rev


def advance(c, project, kind, ident, rev, event):
    c.execute(f'UPDATE {kind}s SET current_revision=?,state_version=state_version+1,last_event_id=? WHERE project_id=? AND id=?',
              (rev,event,project,ident))
