"""Project purpose, participation and explicit reads. Never execution authority."""
from .common import digest, encoded, now, uid, text
from .errors import require

OPS = {
 'project.profile.propose': ({'expected_revision','tagline','body_markdown'}, set(), False),
 'project.profile.save': ({'expected_revision','tagline','body_markdown'}, set(), True),
 'project.profile.accept': ({'revision','digest','expected_revision'}, set(), True),
 'project.profile.reject': ({'revision','digest','expected_revision'}, set(), True),
}

def accepted(core):
    row=core.c.execute('SELECT accepted_revision FROM project_profiles WHERE project_id=?',(core.project,)).fetchone()
    return row[0] if row else None

def version(core, rev):
    row=core.c.execute('SELECT * FROM project_profile_versions WHERE project_id=? AND revision=?',(core.project,rev)).fetchone()
    require(row is not None,'NOT_FOUND','Profile revision unavailable')
    return dict(row)

def participation(core, touch=False):
    ctx=core.context
    identity=getattr(ctx,'participant',None) if ctx else None
    if not identity or not ctx.caller_verified:return None
    require(set(identity)=={'namespace','agent_id','session_id'},'INVALID_INPUT','Invalid adapter participant')
    namespace=text(identity['namespace'],256);session=text(identity['session_id'],512)
    agent=identity['agent_id']
    if agent is not None:text(agent,512)
    key=digest([namespace,agent,session])
    row=core.c.execute('SELECT * FROM project_participations WHERE project_id=? AND identity_namespace=? AND identity_key=?',(core.project,namespace,key)).fetchone()
    if touch and not row:
        stamp=now()
        core.c.execute('INSERT INTO project_participations VALUES (?,?,?,?,?,?,?,?)',(core.project,uid(),namespace,key,agent,session,stamp,stamp))
        row=core.c.execute('SELECT * FROM project_participations WHERE project_id=? AND identity_namespace=? AND identity_key=?',(core.project,namespace,key)).fetchone()
    elif touch and not getattr(ctx,'participant_touched',False):
        core.c.execute('UPDATE project_participations SET last_seen_at=? WHERE project_id=? AND id=?',(now(),core.project,row['id']))
    if touch:ctx.participant_touched=True
    return dict(row) if row else None

def metadata(core):
    rev=accepted(core);actor=participation(core,touch=True)
    last=None
    if actor:
        last=core.c.execute('SELECT profile_revision FROM project_profile_reads WHERE project_id=? AND participation_id=? ORDER BY rowid DESC LIMIT 1',(core.project,actor['id'])).fetchone()
    previous=last[0] if last else None
    return {'available':rev is not None,'revision':rev,'digest':version(core,rev)['content_digest'] if rev else None,
      'last_read_revision':previous,'change_state':'unknown' if not actor else 'unread' if previous is None else 'unchanged' if previous==rev else 'changed',
      'query_ref':{'query':'project.profile','payload':{'revision':rev} if rev else {}}}

def read(core,p):
    meta=metadata(core)
    rev=p.get('revision',meta['revision'])
    require(rev is None or type(rev) is int and rev>0,'INVALID_INPUT','Invalid profile revision')
    budget=p.get('budget',64000)
    require(type(budget) is int and 1024<=budget<=128000,'INVALID_INPUT','Invalid profile budget')
    result={'metadata':meta,'profile':version(core,rev) if rev else None,'proposals':[], 'complete':True}
    # An explicit old accepted revision can be re-read, but candidates are separate.
    if rev is not None:
        require(core.c.execute("SELECT 1 FROM project_profile_reviews WHERE project_id=? AND revision=? AND action='accepted'",(core.project,rev)).fetchone(),'NOT_FOUND','Only accepted profile is readable here')
    if p.get('include_proposals'):
        rows=core.c.execute('SELECT v.* FROM project_profile_versions v WHERE v.project_id=? AND NOT EXISTS (SELECT 1 FROM project_profile_reviews r WHERE r.project_id=v.project_id AND r.revision=v.revision) ORDER BY revision DESC LIMIT 21',(core.project,)).fetchall()
        result['proposals_more']=len(rows)>20
        for row in rows[:20]:
            candidate=dict(row)
            if len(encoded(result).encode())+len(encoded(candidate).encode())+128>budget:
                result['proposals_more']=True;break
            result['proposals'].append(candidate)
    if len(encoded(result).encode())>budget:
        result.update(profile=None,proposals=[],complete=False,required_expansion={'query':'project.profile','payload':{'revision':rev,'budget':128000}})
    # UI views do not mark an agent as having read the introduction.
    if result['complete'] and rev and not p.get('include_proposals') and getattr(core.context,'participant_route','agent')!='ui':
        actor=participation(core)
        if actor:
            core.c.execute('INSERT INTO project_profile_reads VALUES (?,?,?,?,?,?,?,?)',(core.project,uid(),actor['id'],rev,version(core,rev)['content_digest'],now(),getattr(core.context,'participant_route','agent'),uid()))
    return result

def write(core,p):
    op=core.command['command'];head=accepted(core)
    require(p['expected_revision'] is None or type(p['expected_revision']) is int and p['expected_revision']>0,'INVALID_INPUT','Invalid expected revision')
    require(p['expected_revision']==head,'STALE','Project introduction changed; preserve your draft and reload')
    if op in ('project.profile.propose','project.profile.save'):
        tagline=p['tagline'];body=p['body_markdown']
        require(isinstance(tagline,str) and len(tagline)<=256 and isinstance(body,str) and len(body.encode())<=48000,'INVALID_INPUT','Introduction exceeds limits')
        content=digest([tagline,body])
        if head and version(core,head)['content_digest']==content:return {'revision':head,'digest':content,'unchanged':True}
        revision=core.c.execute('SELECT COALESCE(max(revision),0)+1 FROM project_profile_versions WHERE project_id=?',(core.project,)).fetchone()[0]
        core.c.execute('INSERT INTO project_profile_versions VALUES (?,?,?,?,?,?,?,?)',(core.project,revision,head,tagline,body,content,core.event,now()))
        if op.endswith('propose'):return {'revision':revision,'digest':content,'state':'proposed'}
    else:
        revision=p['revision'];v=version(core,revision);content=v['content_digest']
        require(content==p['digest'] and (op.endswith('reject') or v['base_revision']==head),'STALE','Proposal basis changed')
        require(not core.c.execute('SELECT 1 FROM project_profile_reviews WHERE project_id=? AND revision=?',(core.project,revision)).fetchone(),'STALE','Proposal already reviewed')
    action='rejected' if op.endswith('reject') else 'accepted'
    core.c.execute('INSERT INTO project_profile_reviews VALUES (?,?,?,?,?,?)',(core.project,uid(),revision,action,core.event,now()))
    if action=='accepted':
        core.c.execute('INSERT INTO project_profiles VALUES (?,?) ON CONFLICT(project_id) DO UPDATE SET accepted_revision=excluded.accepted_revision',(core.project,revision))
    return {'revision':revision,'digest':content,'state':action}

HANDLERS={name:write for name in OPS}
