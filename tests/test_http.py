import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from reproduction.serve import read_profile, clear_model_environment, install_fakes

tmp = tempfile.TemporaryDirectory()
clear_model_environment()
os.environ.update(read_profile(Path(__file__).resolve().parents[1] / '.env.example'))
os.environ.update(AMI_DB_PATH=str(Path(tmp.name)/'fixture.sqlite3'), AMI_AUTH_TOKEN='offline-test',
                 AMI_AUTH_SCHEME='bearer', OPENAI_API_KEY='offline-test', AMI_EMBED_API_KEY='offline-test',
                 OPENAI_BASE_URL='http://offline.invalid/v1', AMI_EMBED_BASE_URL='http://offline.invalid/v1')
os.environ['TIKTOKEN_CACHE_DIR'] = str(Path(__file__).resolve().parents[1] / 'tokenizer-cache')
install_fakes()
from fastapi.testclient import TestClient
import mneme_asterion.service as s

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm = TestClient(s.app)
        cls.client = cls.cm.__enter__()
        cls.headers = {'Authorization': 'Token offline-test'}
    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)
        s.original.store._conn.close()
        tmp.cleanup()
    def test_health(self): self.assertEqual(self.client.get('/health').status_code, 200)
    def test_auth(self):
        self.assertEqual(self.client.post('/search', json={'user_id':'u','query':'x','top_k':100}).status_code, 401)
    def test_add_idempotent_and_isolation(self):
        p={'request_id':'r1','user_id':'u','session_id':'s','messages':[{'role':'user','content':'I live in Rome.','speaker':'Alice'}]}
        for _ in range(2):self.assertTrue(self.client.post('/add',json=p,headers=self.headers).json()['success'])
        self.assertEqual(len(s.raw_store.history('u')['sessions'][0]['messages']),1)
        self.assertEqual(s.raw_store.history('other')['sessions'],[])
        q={**p,'messages':[{'role':'user','content':'Different content'}]}
        self.assertEqual(self.client.post('/add',json=q,headers=self.headers).status_code,409)
        staged=s.original.AddRequest(request_id='failed',user_id='other',session_id='s',messages=[{'role':'user','content':'Uncommitted data'}])
        s.raw_store.stage(staged)
        self.assertEqual(s.raw_store.history('other')['sessions'],[])
    def test_redacted_same_id_serializes_modified_text(self):
        old=[{'id':'1','content':'withdrawn value','score':0.9}]
        ev=[{'id':'1','text':'safe retained text','source_ids':['s']}]
        self.assertEqual(s.encode_result(ev,old,100)[0]['content'],'safe retained text')
        self.assertEqual(s.encode_result(ev,old,0),[])
    def test_p2_http_route_uses_transformed_text(self):
        with patch.object(s.raw_store,'history',return_value={'sessions':[{'timestamp':None,'messages':[{'role':'user','text':'Source text','speaker':'User'}]}]}), patch.object(s.original.native,'search',return_value={'data':[{'id':'a','content':'original'}]}), patch.object(s,'generate_r1q',return_value=([{'id':'a','text':'original'}],{})), patch.object(s,'generate_state_policy',return_value=([{'id':'a','text':'redacted and notice'}],{})):
            r=self.client.post('/search',headers=self.headers,json={'user_id':'u','query':'x','top_k':100})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['data'][0]['content'],'redacted and notice')
            self.assertEqual(r.json()['method'],'ScopedStateV4')
    def test_transient_enrichment_failure_preserves_available_result(self):
        with patch.object(s.raw_store,'history',return_value={'sessions':[{'timestamp':None,'messages':[{'role':'user','text':'Source text','speaker':'User'}]}]}), patch.object(s.original.native,'search',return_value={'data':[]}), patch.object(s,'generate_r1q',side_effect=s.llm.UpstreamUnavailable(503,'fixture',2)):
            r=self.client.post('/search',headers=self.headers,json={'user_id':'u','query':'x','top_k':100})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['data'],[])

    def test_scoped_state_hook_preserves_other_owner_and_serializes_redaction(self):
        history={'sessions':[{'timestamp':None,'messages':[
            {'role':'user','speaker':'user','text':'My project color is R10.','source_id':'old'},
            {'role':'user','speaker':'user','text':'Please forget my project color.','source_id':'control'},
            {'role':'user','speaker':'user','text':"My colleague's project color is R20.",'source_id':'other'}]}]}
        evidence=[{'id':'old','text':'My project color is R10.','source_ids':['old']},
                  {'id':'other','text':"My colleague's project color is R20.",'source_ids':['other']}]
        with patch.dict(os.environ,{'P2_SCOPED_STATE':'1'}), patch.object(s.raw_store,'history',return_value=history), patch.object(s.original.native,'search',return_value={'data':[{'id':'old','content':'My project color is R10.'}]}), patch.object(s,'generate_r1q',return_value=(evidence,{})), patch.object(s,'generate_state_policy',return_value=(evidence,{})):
            response=self.client.post('/search',headers=self.headers,json={'user_id':'u','query':'What is my project color?','top_k':100})
            self.assertEqual(response.status_code,200)
            text='\n'.join(e['content'] for e in response.json()['data'])
            self.assertNotIn('R10',text)
            # Query-local projection excludes both the withdrawn value and
            # another owner's value from this current-user slot.
            self.assertNotIn('R20',text)
            self.assertIn('current user',text)
            other=self.client.post('/search',headers=self.headers,json={'user_id':'u','query':"What is my colleague's project color?",'top_k':100})
            self.assertEqual(other.status_code,200)
            other_text='\n'.join(e['content'] for e in other.json()['data'])
            self.assertIn('R20',other_text)
            self.assertNotIn('R10',other_text)
            self.assertIn('R10',history['sessions'][0]['messages'][0]['text'])


if __name__=='__main__':unittest.main()
