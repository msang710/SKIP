"""No timer sends a durable row. Only its live adapter can claim and send it."""
import json
import time
from .authority import Principal
from .common import digest, now, uid
from .errors import CoreError, require
from .execution import basis, risk_basis, transition
from . import records


class Delivery:
    def __init__(self, core, context):
        self.core,self.context=core,context

    def _begin(self, action):
        c=self.core
        c.project,c.context=self.context.project_id,self.context
        c.principal=Principal(c.project,self.context.context_id,kind='system',verifier='trusted-host-adapter')
        c.key,c.counter=uid(),0
        c.command={'command':action}
        c.interaction=c._interaction(c.principal,c.command)
        c.event=c.event_record(action)

    def claim(self, execution_id):
        self.context.check(start=True)
        c=self.core
        with c.db.transaction():
            self._begin('delivery.claim')
            x=c.one('executions',execution_id)
            require(x['dispatch_context_digest']==self.context.fingerprint,'CONTEXT_EXPIRED','Execution belongs to a previous connection')
            d=dict(c.c.execute('SELECT * FROM deliveries WHERE project_id=? AND execution_id=?',(c.project,execution_id)).fetchone())
            require(x['state']=='prepared' and d['state']=='pending','CONFLICT','Delivery is not available for sending')
            a=c.one('authorizations',x['authorization_id'])
            require(not c.c.execute('SELECT 1 FROM authorization_revocations WHERE project_id=? AND authorization_id=?',(c.project,a['id'])).fetchone(),
                    'STALE','Execution permission was revoked')
            b=basis(c,x['work_item_id'],x['work_revision'])
            risks,saved=risk_basis(c,{'goal_risk_id':a['goal_risk_id'],'change_risk_id':a['change_risk_id']},b)
            require(digest({'basis':b,'snapshot':saved['digest'],'risks':[r['digest'] for r in risks]})==a['basis_digest'],
                    'STALE','Execution basis changed')
            self.context.check(start=True)
            lease=uid()
            transition(c,'deliveries',d,'dispatching',lease_owner=lease,lease_until=str(time.time()+30),attempt_count=d['attempt_count']+1)
            records.insert(c.c,'delivery_attempts',dict(project_id=c.project,delivery_id=d['id'],attempt_no=d['attempt_count']+1,
                started_event_id=c.event,started_at=now()))
            return {'execution_id':x['id'],'delivery_id':d['id'],'lease':lease,'message_key':d['message_key'],'payload':json.loads(d['payload'])}

    def acknowledgement(self, claim, outcome, *, receipt=None):
        """Called only by a trusted transport, never from a model-visible tool."""
        require(outcome in ('accepted','rejected','unknown'),'INVALID_INPUT','Invalid delivery receipt')
        if outcome!='unknown':
            require(isinstance(receipt,dict) and receipt.get('message_key')==claim['message_key'],
                    'INVALID_INPUT','Receipt must identify this exact message')
        c=self.core
        with c.db.transaction():
            self._begin('delivery.'+outcome)
            d=c.one('deliveries',claim['delivery_id']); x=c.one('executions',claim['execution_id'])
            require(d['execution_id']==x['id'] and d['message_key']==claim['message_key'] and
                    d['lease_owner']==claim['lease'],'CONFLICT','Delivery claim mismatch')
            require(d['state'] in ('dispatching','delivery_unknown'),'CONFLICT','Delivery already resolved')
            target={'accepted':'accepted','rejected':'failed','unknown':'delivery_unknown'}[outcome]
            transition(c,'deliveries',d,target,last_error=None if outcome=='accepted' else outcome)
            attempt=c.c.execute('SELECT * FROM delivery_attempts WHERE project_id=? AND delivery_id=? AND attempt_no=?',
                                (c.project,d['id'],d['attempt_count'])).fetchone()
            if attempt and attempt['finished_at'] is None:
                c.c.execute('UPDATE delivery_attempts SET finished_at=?,outcome=?,host_message_key=? WHERE project_id=? AND delivery_id=? AND attempt_no=?',
                            (now(),outcome,claim['message_key'] if receipt else None,c.project,d['id'],d['attempt_count']))
            if outcome=='accepted':
                state='cancel_requested' if x['state']=='cancel_requested' else 'accepted'
                transition(c,'executions',x,state,result_receipt_digest=digest(receipt),started_at=now())
            elif outcome=='rejected':
                transition(c,'executions',x,'failed',finished_at=now())
            return {'execution_id':x['id'],'delivery_state':target}

    def send(self, execution_id, sender):
        claim=self.claim(execution_id)
        try:
            # A context switch here makes delivery uncertain; it never changes the target.
            self.context.check(start=True)
            receipt=sender(claim['payload'],claim['message_key'])
        except BaseException:
            self.acknowledgement(claim,'unknown')
            raise
        return self.acknowledgement(claim,'accepted',receipt=receipt)

    def finish(self, execution_id, receipt, *, state='finished', reconciled=False):
        require(state in ('running','finished','failed','cancelled','cancellation_unknown'),'INVALID_INPUT','Invalid execution state')
        c=self.core
        with c.db.transaction():
            self._begin('execution.receipt')
            x=c.one('executions',execution_id)
            d=dict(c.c.execute('SELECT * FROM deliveries WHERE project_id=? AND execution_id=?',(c.project,execution_id)).fetchone())
            require(isinstance(receipt,dict) and receipt.get('message_key')==d['message_key'],'INVALID_INPUT','Exact message receipt required')
            require(reconciled or x['dispatch_context_digest']==self.context.fingerprint,'CONTEXT_EXPIRED','Original live receipt context required')
            require(x['state'] in ('accepted','running','cancel_requested','cancellation_unknown'),'CONFLICT','Execution not accepted')
            require(not (x['state']=='cancel_requested' and state=='running'),'CONFLICT','Cancellation is pending')
            transition(c,'executions',x,state,result_receipt_digest=digest(receipt),
                       finished_at=now() if state in ('finished','failed','cancelled') else None)
            return {'execution_id':execution_id,'state':state,'validation_complete':False}

    def expire_claims(self):
        """Recovery marks uncertainty, never retransmits or releases active work."""
        c=self.core
        with c.db.transaction():
            self._begin('delivery.recover')
            rows=c.c.execute("SELECT * FROM deliveries WHERE project_id=? AND state='dispatching' AND CAST(lease_until AS REAL)<?",
                             (c.project,time.time())).fetchall()
            for row in rows:
                transition(c,'deliveries',dict(row),'delivery_unknown',last_error='connection or receipt expired')
            return {'marked_unknown':len(rows),'sent':0}

    def reconcile(self, execution_id, receipt, *, outcome, state=None):
        """Trusted host lookup only; receipt facts never supply a dispatch route.

        Adapters without an exact-message lookup capability must not call this.
        This is deliberately absent from model tools and general CLI commands.
        """
        self.context.check()
        require(outcome in ('accepted','rejected') and (state is None or (outcome=='accepted' and state in ('running','finished','failed','cancelled','cancellation_unknown'))),'INVALID_INPUT','Invalid verified receipt outcome')
        require(isinstance(receipt,dict) and bool(receipt.get('lookup_receipt')),
                'INVALID_INPUT','A verified exact-message host lookup receipt is required')
        c=self.core
        with c.db.transaction(write=False):
            x=c.c.execute('SELECT * FROM executions WHERE project_id=? AND id=?',(self.context.project_id,execution_id)).fetchone()
            require(x is not None,'NOT_FOUND','Execution unavailable')
            d=c.c.execute('SELECT * FROM deliveries WHERE project_id=? AND execution_id=?',(self.context.project_id,execution_id)).fetchone()
            require(receipt.get('message_key')==d['message_key'],'INVALID_INPUT','Receipt belongs to another message')
            claim={'execution_id':execution_id,'delivery_id':d['id'],'message_key':d['message_key'],'lease':d['lease_owner']}
            delivery_state=d['state']
        if delivery_state in ('dispatching','delivery_unknown'):
            result=self.acknowledgement(claim,outcome,receipt=receipt)
        else:
            require(delivery_state=='accepted' and outcome=='accepted','CONFLICT','Receipt does not match resolved delivery')
            result={'execution_id':execution_id,'delivery_state':'accepted'}
        if state:
            require(outcome=='accepted','INVALID_INPUT','Only an accepted message can have a terminal turn receipt')
            result=self.finish(execution_id,receipt,state=state,reconciled=True)
        return dict(result,route_restored=False,sent=0)
