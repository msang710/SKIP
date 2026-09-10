"""Private native-adapter channel; not an MCP tool or a public approval CLI.

The parent owns user provenance and verified host identity. The random channel
secret is never exposed to a model. As with the installed plugin, this does not
protect against arbitrary code running with the same OS user privileges.
"""
import hmac
import json
import os
import sys
from pathlib import Path
from .authority import ExecutionContext,Principal
from .common import uid,encoded
from .db import Database,default_path
from .delivery import Delivery
from .errors import CoreError,require
from .service import Core


class NativeBridge:
    def __init__(self,db_path= None):
        self.path=Path(db_path) if db_path else default_path()
        self.context=None;self.db=None;self.core=None;self.claims={};self.identity=()

    def close(self):
        if self.context:self.context.close()
        if self.db:self.db.close()
        self.db=self.core=None
        self.claims.clear()

    def dispatch(self,p):
        operation=p['operation']
        if operation=='connect':
            self.close()
            self.identity=tuple(p['identity'])
            require(len(self.identity)>=3 and all(isinstance(x,str) for x in self.identity) and all(self.identity[:3]),'INVALID_INPUT','Verified host identity required')
            self.context=ExecutionContext(p['project_id'],{k:Path(v).resolve(strict=True) for k,v in p['sources'].items()},
                self.identity,lambda:self.identity,can_start=p.get('can_start') is True)
            return {'connected':True,'context_id':self.context.context_id,'capabilities':{'start_turn':self.context.can_start}}
        require(self.context is not None,'CONTEXT_EXPIRED','Connect the native host first')
        if operation=='disconnect':self.close();return {'connected':False}
        if operation=='invalidate':
            self.context.close();return {'connected':False}
        self.context.check()
        if not self.db:
            create=operation=='user' and p.get('command',{}).get('command')=='project.activate'
            self.db=Database(self.path,create=create);self.core=Core(self.db)
        principal=Principal(self.context.project_id,self.context.context_id)
        if operation=='query':return self.core.query(p['query'],p.get('payload',{}),principal,self.context)
        if operation=='agent':return self.core.execute(p['command'],principal,self.context)
        if operation=='card':
            # The parent only calls this for its current UI and displays this exact command.
            ticket=self.context.issue(p['command']);return {'ticket':ticket}
        if operation=='user':
            event=p['user_event']
            principal=Principal(self.context.project_id,self.context.context_id,kind='human',method='native_user_action',
                verifier='native-adapter-assertion',event_key=event['id'],user_text=event['text'])
            command=p['command']
            if command['command'] not in ('project.activate','request.submit'):
                # Idempotent receipt is scoped to this live context. A replay must not consume a ticket twice.
                old=self.db.connection.execute('SELECT command_digest FROM command_receipts WHERE project_id=? AND principal_digest=? AND command_key=?',
                    (principal.project_id,principal.fingerprint,command['key'])).fetchone()
                if not old:self.context.consume(p['ticket'],command,principal)
            return self.core.execute(command,principal,self.context)
        delivery=Delivery(self.core,self.context)
        if operation=='claim':
            claim=delivery.claim(p['execution_id']);self.claims[claim['delivery_id']]=claim;return claim
        if operation=='ack':
            claim=self.claims.get(p['delivery_id'])
            require(claim is not None,'CONTEXT_EXPIRED','Current delivery claim unavailable')
            return delivery.acknowledgement(claim,p['outcome'],receipt=p.get('receipt'))
        if operation=='finish':return delivery.finish(p['execution_id'],p['receipt'],state=p['state'])
        if operation=='reconcile':return delivery.reconcile(p['execution_id'],p['receipt'],outcome=p['outcome'],state=p.get('state'))
        if operation=='recover':return delivery.expire_claims()
        raise CoreError('INVALID_INPUT','Unknown native operation')


def main():
    secret=os.environ.pop('SKIP_NATIVE_CHANNEL_SECRET','')
    require(len(secret)>=32,'USER_ACTION_REQUIRED','A private parent adapter channel is required')
    bridge=NativeBridge(os.environ.get('SKIP_DB_PATH'))
    try:
        while True:
            line=sys.stdin.buffer.readline(600001)
            if not line:break
            ident=None
            try:
                require(len(line)<=600000 and line.endswith(b'\n'),'INVALID_INPUT','Frame exceeds bound')
                value=json.loads(line);ident=value.get('id')
                require(isinstance(value.get('secret'),str) and hmac.compare_digest(value['secret'],secret),
                        'USER_ACTION_REQUIRED','Invalid parent channel')
                result=bridge.dispatch(value['payload'])
                response={'id':ident,'result':result}
            except CoreError as exc:response={'id':ident,'error':exc.result()}
            except (ValueError,KeyError,TypeError,OSError) as exc:
                response={'id':ident,'error':CoreError('INVALID_INPUT',str(exc)).result()}
            print(encoded(response),flush=True)
    finally:bridge.close()

if __name__=='__main__':main()
