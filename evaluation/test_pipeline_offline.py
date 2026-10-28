import sys,json,tempfile,importlib.util,os
from pathlib import Path
from unittest.mock import patch
import httpx
import argparse
a=argparse.ArgumentParser();a.add_argument('--benchmark-root',required=True);args=a.parse_args()
root=Path(args.benchmark_root).resolve();sys.path.insert(0,str(root/'src'))
from memory_benchmark.pipeline.prepare import prepare
from memory_benchmark.runtime.model_client import FixtureClient
suite=json.loads((root/'configs/suites/smoke.json').read_text())
for cfg in suite['benchmarks'].values():
 for key in ('data_file','data_dir'):
  if key in cfg:cfg[key]=str(root/cfg[key])
runtime=json.loads((root/'configs/runtime.json').read_text());runtime['env_file']='unused-offline'
module_path=Path(__file__).resolve().with_name('run_prepared.py')
spec=importlib.util.spec_from_file_location('eval_entry',module_path);entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
realclient=httpx.Client;calls=[]
def handle(r):
 value=json.loads(r.content);calls.append(r.url.path)
 assert 'gold' not in value and 'target' not in value
 if r.url.path=='/add':return httpx.Response(200,json={'success':True,**{k:value[k] for k in ['request_id','user_id','session_id']}})
 return httpx.Response(200,json={'method':'ScopedStateV4','data':[{'id':'synthetic','content':'Synthetic source text.'}]})
with tempfile.TemporaryDirectory(dir='.') as d:
 p=Path(d).resolve();prepare(suite,runtime,p/'prepared')
 with patch.dict(os.environ,{'P2_MEMORY_TOKEN':'offline-fixture'}),patch.object(sys,'argv',['eval','--benchmark-root',str(root),'--prepared',str(p/'prepared'),'--output',str(p/'out')]),patch('httpx.Client',side_effect=lambda **kw:realclient(**kw,transport=httpx.MockTransport(handle))),patch('memory_benchmark.runtime.model_client.Gateway',side_effect=lambda *a,**kw:FixtureClient()):
  entry.main()
 result=json.loads((p/'out/status.json').read_text());assert result['status']=='complete' and result['scored']==3,result
 summary={'status':'passed','synthetic_questions':3,'api_calls':0,'mock_http_calls':calls,'quality_score':None,'purpose':'new evaluation entry offline pipeline integration only'}
 # Only print synthetic validation, never a method quality score.
 print(summary)
