"""Shared current decision selection projection for every read adapter."""
def attach(core, item):
    row=core.c.execute('SELECT s.*, EXISTS(SELECT 1 FROM selection_revocations v WHERE v.project_id=s.project_id AND v.selection_id=s.id) revoked '
        'FROM selections s WHERE s.project_id=? AND s.decision_id=? '
        'AND NOT EXISTS(SELECT 1 FROM selections n WHERE n.project_id=s.project_id AND n.supersedes_id=s.id) '
        'ORDER BY (SELECT sequence FROM events e WHERE e.project_id=s.project_id AND e.id=s.event_id) DESC LIMIT 1',
        (core.project,item['id'])).fetchone()
    stale=bool(row and row['decision_revision']!=item['revision'])
    valid=bool(row and not row['revoked'] and not stale and item['lifecycle']=='active')
    selection={k:row[k] for k in row.keys() if k!='revoked'} if valid else None
    item['selection']=selection
    item['selection_stale']=stale
    item['selection_state']='revoked' if row and row['revoked'] else 'stale' if stale else 'selected' if valid else 'unselected'
    item['selected_option']=next((o for o in item['children']['options'] if selection and o['option_id']==selection['option_id']),None)
    item['action_state']='needs_options' if len(item['children']['options'])<2 else 'selected' if valid else 'needs_selection'
    item['action_reason']='선택지가 기록되지 않았습니다. 에이전트가 질문과 선택지를 정리해야 합니다.' if item['action_state']=='needs_options' else None
    return item
