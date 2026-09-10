import json
from pathlib import Path
import tempfile
import unittest
from adapters.codex.provenance import current_user,proposal_reply,EntryError

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.thread='01234567-1234-1234-1234-012345678901'
        folder=self.root/'2026/09/11';folder.mkdir(parents=True)
        self.path=folder/('rollout-'+self.thread+'.jsonl')
        self.items=[{'type':'session_meta','payload':{'id':self.thread,'cwd':str(self.root)}}]
    def add(self,role,text,id):
        self.items.append({'type':'response_item','payload':{'type':'message','role':role,'id':id,'content':[{'type':'input_text' if role=='user' else 'output_text','text':text}]}})
        self.path.write_text(''.join(json.dumps(v)+'\n' for v in self.items))
    def read(self):return current_user(self.root,self.thread,self.root)
    def test_environment_supplement_preserves_actual_request(self):
        self.add('user','구현해','u1');self.add('user','<environment_context><current_date>2026-09-11</current_date><timezone>Asia/Seoul</timezone></environment_context>','env')
        self.assertEqual(self.read()['id'],'u1');self.assertEqual(self.read()['supplements'][0]['role_basis'],'parser')
        self.add('user','<environment_context><current_date>today</current_date></environment_context> 취소해','bad')
        with self.assertRaises(EntryError):self.read()
    def test_approval_requires_unique_preceding_proposal(self):
        self.add('user','검토해','u1');self.add('assistant','변경 범위 제안 SKIP-PROPOSAL:p:1:abc','a1');self.add('user','그래 승인이야','u2')
        c=[{'id':'p','revision':1,'digest':'abc'}]
        self.assertEqual(proposal_reply(self.read(),c),('p',1))
        with self.assertRaises(EntryError):proposal_reply(self.read(),[{'id':'p','revision':2,'digest':'abc'}])
        self.add('assistant','다른 질문','a2');self.add('user','그래 승인이야','u3')
        with self.assertRaises(EntryError):proposal_reply(self.read(),c)
