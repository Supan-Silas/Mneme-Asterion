import unittest
from unittest.mock import patch
from tests import test_http as fixture
from app import llm, runtime, config, store
from app.availability import enrichment_budget
from mneme_asterion.availability import retrieve, protect
from memory_benchmark.pipeline.context import GPTTokenizer
from fastapi.testclient import TestClient

class AvailabilityTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        if store._conn is not None:store._conn.close()
    def failure(self):return llm.UpstreamUnavailable(503, 1, 'injected invalid response')

    def test_optional_enrichments_degrade(self):
        cases=[(llm.extract_facts,('text',),[]),
               (llm.classify_update_intent,('0 | I: A fact.',),[]),
               (llm.extract_updates,('0 | I: change',[(0,'change')]),[]),
               (llm.recall_question,('question',None),None),
               (llm.verify_replaced_v2,('update',['old']),None),
               (llm.classify_question,('question',None),None)]
        for fn,args,expected in cases:
            with self.subTest(fn=fn.__name__),patch.object(runtime,'chat',side_effect=self.failure()):
                self.assertEqual(fn(*args),expected)

    def test_permanent_errors_do_not_become_success(self):
        with patch.object(runtime,'chat',side_effect=runtime.PermanentProviderError('test',401)):
            with self.assertRaises(runtime.PermanentProviderError):llm.extract_facts('text')

    def test_child_budget_does_not_cancel_parent(self):
        with runtime.request_scope():
            before=runtime.remaining()
            with enrichment_budget(.05):self.assertLess(runtime.remaining(),.06)
            self.assertGreater(runtime.remaining(),before-1)

    def test_retrieval_falls_back_to_literal_source(self):
        source={'id':'s','body':'Alice likes apples.', 'source_ids':['original']}
        def fail(*a):raise self.failure()
        out,trace=retrieve(fail,'Alice apples',[],[source],None,GPTTokenizer('gpt-4o-mini'))
        self.assertTrue(trace['degraded']);self.assertEqual(out[0]['text'].split('\n',1)[1],source['body'])

    def test_privacy_failure_contains_no_old_value(self):
        def fail(*a):raise self.failure()
        out,trace=protect(fail,'color',[{'text':'Secret amber'}],[],None,None)
        self.assertTrue(trace['degraded']);self.assertNotIn('amber',str(out))

    def test_http_add_survives_all_llm_failure_and_is_idempotent(self):
        s=fixture.s
        with TestClient(s.app) as client,patch.object(runtime,'chat',side_effect=self.failure()):
            data={'request_id':'rc15-add','user_id':'rc15-user','session_id':'s',
                  'messages':[{'role':'user','content':'My project is AMBER.'}]}
            headers={'Authorization':'Token offline-test'}
            first=client.post('/add',json=data,headers=headers)
            self.assertEqual(first.status_code,200,first.text)
            self.assertTrue(first.json()['success'])
            self.assertTrue(store.get('rc15-user').items)
            self.assertEqual(client.post('/add',json=data,headers=headers).status_code,200)
            self.assertEqual(len(s.raw_store.history('rc15-user')['sessions'][0]['messages']),1)
            self.assertEqual(s.raw_store.history('unrelated')['sessions'],[])
            result=client.post('/search',json={'user_id':'rc15-user','query':'project','top_k':100},headers=headers)
            self.assertEqual(result.status_code,200,result.text)
            self.assertIn('AMBER',str(result.json()))

    def test_embedding_failure_still_rejects_add(self):
        s=fixture.s
        with TestClient(s.app) as client,patch.object(s.original.native,'encode_or_unavailable',side_effect=self.failure()):
            data={'request_id':'rc15-embed-fail','user_id':'embed-fail','session_id':'s',
                  'messages':[{'role':'user','content':'Do not expose incomplete write.'}]}
            response=client.post('/add',json=data,headers={'Authorization':'Token offline-test'})
            self.assertEqual(response.status_code,503)
            self.assertEqual(s.raw_store.history('embed-fail')['sessions'],[])

if __name__=='__main__':unittest.main()
