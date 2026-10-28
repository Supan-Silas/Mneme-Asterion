import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx
from evaluation.run_prepared import request,add_payload
from tools.verify_release import verify
from launch import configure

class ReleaseTests(unittest.TestCase):
    def test_exact_source(self):self.assertTrue(verify()['pass'])
    def test_blank_template_fails_before_service_import(self):
        with self.assertRaises(ValueError):configure(Path(__file__).resolve().parents[1]/'.env.example')
    def test_add_payload_preserves_source_and_scope(self):
        m=SimpleNamespace(role='user',text='original',speaker='Alice',source_id='m1')
        c=SimpleNamespace(session_id='s',chunk_id='c1',timestamp=None,messages=[m])
        p=add_payload('u',c)
        self.assertEqual(p['request_id'],'u:c1');self.assertEqual(p['messages'][0]['content'],'original')
        self.assertEqual(p['messages'][0]['source_id'],'m1');self.assertIsNone(p['messages'][0]['timestamp'])
    def test_503_then_success_retries_same_request(self):
        seen=[]
        def handle(r):
            seen.append(r.content)
            return httpx.Response(503 if len(seen)==1 else 200,json={'success':True})
        with httpx.Client(base_url='http://fixture.invalid',transport=httpx.MockTransport(handle)) as c,patch('evaluation.run_prepared.time.sleep'):
            self.assertTrue(request(c,'/add',{'request_id':'same'})['success'])
        self.assertEqual(len(seen),2);self.assertEqual(seen[0],seen[1])
    def test_search_409_never_retries(self):
        seen=[]
        def handle(r):seen.append(r);return httpx.Response(409)
        with httpx.Client(base_url='http://fixture.invalid',transport=httpx.MockTransport(handle)) as c,patch('evaluation.run_prepared.time.sleep'):
            with self.assertRaises(httpx.HTTPStatusError):request(c,'/search',{})
        self.assertEqual(len(seen),1)
    def test_retry_limit_keeps_failure(self):
        seen=[]
        def handle(r):seen.append(r);return httpx.Response(429)
        with httpx.Client(base_url='http://fixture.invalid',transport=httpx.MockTransport(handle)) as c,patch('evaluation.run_prepared.time.sleep'):
            with self.assertRaises(httpx.HTTPStatusError):request(c,'/search',{},attempts=3)
        self.assertEqual(len(seen),3)

if __name__=='__main__':unittest.main()
