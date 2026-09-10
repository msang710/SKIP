import unittest
from tests.core.helpers import Fixture
from skip_core.authority import Principal
from skip_core.errors import CoreError

class SavedRequestTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.addCleanup(self.f.close)
    def test_saved_ui_requests_are_paged_and_exact_not_latest_chat(self):
        f=self.f
        for text in ('first saved request','second saved request'):
            f.call('request.submit',{'text':text,'operation':'investigate'},True,words=text)
        actor=f.actor()
        page=f.core.query('request.list',{'limit':1},actor)['data']
        self.assertEqual(len(page['items']),1);self.assertIsNotNone(page['next_cursor'])
        a=page['items'][0]
        detail=f.core.query('request',{'id':a['id']},actor)['data']
        self.assertEqual(detail['intent'],a['intent']);self.assertEqual(len(detail['goals']),1)
        second=f.core.query('request.list',{'limit':1,'cursor':page['next_cursor']},actor)['data']
        self.assertNotEqual(second['items'][0]['id'],a['id'])
        for table in ('authorizations','executions','selections'):
            self.assertEqual(f.db.connection.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        with self.assertRaises(CoreError):f.core.query('request',{'id':a['id']},Principal('other','read'))
    def test_native_decision_remains_selectable(self):
        f=self.f;f.request()
        d=f.publish('decision',{'question':'Choose','rationale':'Reason','risk_summary':'Risk'}, {'options':[
            {'option_id':'a','label':'A','description':'A','consequences':'A','recommended':1,'position':0},
            {'option_id':'b','label':'B','description':'B','consequences':'B','recommended':0,'position':1}]})
        card=f.core.query('inbox',{'goal_id':f.goal},f.actor())['data']['items'][0]
        self.assertEqual(card['action_state'],'needs_selection')
        f.call('decision.select',{'decision_id':d['id'],'revision':d['revision'],'option_id':'a'},True)
        card=f.core.query('inbox',{'goal_id':f.goal},f.actor())['data']['items'][0]
        self.assertEqual(card['action_state'],'selected')

    def test_skill_attachment_is_not_a_saved_user_request(self):
        import json
        from adapters.codex.provenance import current_user, infer_operation
        root=self.f.root/'sessions';folder=root/'2026/09/10';folder.mkdir(parents=True)
        thread='01234567-1234-1234-1234-012345678901'
        content=[{'type':'session_meta','payload':{'id':thread,'cwd':str(self.f.root)}}]
        for ident,text in [('user1','새 목표 "example" 생성해봐'),('attachment','<skill>\n<name>skip</name>\n<path>/installed/SKILL.md</path>\nimplement code\n</skill>')]:
            content.append({'type':'response_item','payload':{'type':'message','role':'user','id':ident,'content':[{'type':'input_text','text':text}]}})
        path=folder/('rollout-'+thread+'.jsonl');path.write_text(''.join(json.dumps(v)+'\n' for v in content))
        actual=current_user(root,thread,self.f.root)
        self.assertEqual(actual['id'],'user1');self.assertEqual(infer_operation(actual['text']),'plan')
