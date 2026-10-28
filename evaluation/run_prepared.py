"""Evaluate a memory HTTP service using the a3f9610 benchmark Reader and Judge."""
import argparse
from datetime import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

def add_payload(scope, chunk):
    return {'request_id': scope+':'+(getattr(chunk,'chunk_id',None) or chunk.session_id),
            'user_id': scope, 'session_id': chunk.session_id,
            'messages': [{'role':m.role,'content':m.text,'speaker':m.speaker,'source_id':m.source_id,
                          'timestamp': int(datetime.fromisoformat(chunk.timestamp).timestamp()*1000) if chunk.timestamp else None}
                         for m in chunk.messages]}

def request(client, path, payload, attempts=3):
    import httpx
    for attempt in range(attempts):
        try:
            r = client.post(path,json=payload)
            transient = r.status_code in {408,425,429,500,502,503,504,524} or (path=='/add' and r.status_code==409)
            if not transient or attempt == attempts-1:
                r.raise_for_status()
                return r.json()
        except httpx.TransportError:
            if attempt == attempts-1: raise
        time.sleep(min(2**attempt,8))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--benchmark-root',required=True,help='benchmark directory at commit a3f9610')
    p.add_argument('--prepared',required=True)
    p.add_argument('--output',required=True,help='NEW output directory; this simple runner does not resume')
    p.add_argument('--url',default='http://127.0.0.1:8014')
    p.add_argument('--method',default='ScopedStateV4',choices=['ScopedStateV4','P2'])
    p.add_argument('--check',action='store_true',help='Validate inputs only, no API calls')
    a=p.parse_args()
    # Import full reference framework, never the small runtime namespace in the P2 service.
    sys.path.insert(0,str(Path(a.benchmark_root).resolve()/'src'))
    from memory_benchmark.pipeline.prepare import verify_prepared
    from memory_benchmark.pipeline.runner import validate_runtime
    from memory_benchmark.pipeline.ingestion import plan
    from memory_benchmark.pipeline.reader import answer
    from memory_benchmark.pipeline.evaluate import evaluate
    from memory_benchmark.pipeline.aggregate import import_native,summarize
    from memory_benchmark.pipeline.context import GPTTokenizer
    from memory_benchmark.runtime.artifacts import read_json,rows,write_json,contract_hash
    from memory_benchmark.runtime.model_client import Gateway
    from memory_benchmark.schemas import History,Query,Target
    root=Path(a.prepared).resolve(); manifest=verify_prepared(root)
    runtime=manifest['runtime'];validate_runtime(runtime)
    cases=list(rows(root/'cases.jsonl'))
    # This legacy helper is an open-QA example. Do not silently omit options.
    # Validate every question before Add or any other paid operation.
    for case in cases:
        for q in rows(root/case['queries']):
            if q.get('all_options') or q.get('options'):
                raise ValueError('This example supports open QA only; use a full benchmark HTTP adapter that forwards options for multiple-choice data')
    if runtime.get('top_k')!=100 or runtime.get('answer_input_token_limit')!=117760 or runtime.get('answer_context_policy')!='aml_ranked_prefix_v1':
        raise ValueError('Use frozen top_k=100 / AML 117760 input-window prepared data')
    if a.check:
        print(json.dumps({'status':'inputs_valid','histories':len(cases),'api_calls':0}));return
    token=os.environ.get('P2_MEMORY_TOKEN') or getpass.getpass('Memory service token: ')
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    run_id=uuid.uuid4().hex
    write_json(out/'identity.json',{'prepared_sha256':contract_hash(manifest),'run_id':run_id,
                                  'method':a.method,'runner':'sequential-http-v1','url':a.url,
                                  'cost_scope':'Reader/Judge ledger excludes remote Add/Search provider costs'})
    def persist(path,row):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    import httpx
    client=None; started=time.monotonic();scores=[]
    try:
        tok=GPTTokenizer(runtime['model'])
        # Separate service receives only histories and questions, never targets.
        with httpx.Client(base_url=a.url,headers={'Authorization':'Bearer '+token},timeout=1800,trust_env=False) as http:
            for index,case in enumerate(cases):
                folder=out/str(index);scope='team-eval:'+run_id+':'+str(index)
                history=History.from_wire(read_json(root/case['history']))
                chunks,_=plan(history,runtime.get('add_chunk_policy'))
                for chunk in chunks:
                    payload=add_payload(scope,chunk);result=request(http,'/add',payload)
                    if result.get('success') is not True or any(result.get(k)!=payload[k] for k in ('request_id','user_id','session_id')):
                        raise ValueError('Invalid Add contract')
                    persist(folder/'adds.jsonl',{'request_id':payload['request_id'],'success':True})
                for q in rows(root/case['queries']):
                    query=Query(**q)
                    result=request(http,'/search',{'query':query.text,'user_id':scope,'top_k':100})
                    if result.get('method') != a.method:
                        raise ValueError('Search method identity does not match --method')
                    evidence=[{'id':x['id'],'text':x['content'],'source_ids':x.get('source_ids',[]),'timestamp':None,'metadata':{}} for x in result['data']]
                    persist(folder/'retrievals.jsonl',{'id':query.qa_id,'evidence':evidence})
        client=Gateway(runtime,out/'reader_judge'/'usage.json')
        for index,case in enumerate(cases):
            folder=out/str(index);history=History.from_wire(read_json(root/case['history']))
            retrieved={r['id']:r['evidence'] for r in rows(folder/'retrievals.jsonl')}
            for q in rows(root/case['queries']):
                query=Query(**q)
                persist(folder/'answers.jsonl',answer(query,retrieved[query.qa_id],history.speakers,client,tok,runtime))
        # Only now load scoring labels, after every answer is durably saved.
        for index,case in enumerate(cases):
            folder=out/str(index)
            queries={q['qa_id']:Query(**q) for q in rows(root/case['queries'])}
            targets={t['qa_id']:Target(**t) for t in rows(root/case['targets'])}
            for record in rows(folder/'answers.jsonl'):
                native=evaluate(queries[record['id']],targets[record['id']],record,client,runtime)
                persist(folder/'native_scores.jsonl',native)
                scores.extend(import_native(manifest,[native],case['benchmark'],a.method,run_id))
        write_json(out/'summary.json',summarize(manifest,scores))
        write_json(out/'status.json',{'status':'complete','scored':len(scores),'wall_seconds':time.monotonic()-started})
    except BaseException as e:
        write_json(out/'status.json',{'status':'incomplete','error_type':type(e).__name__,
                                    'wall_seconds':time.monotonic()-started,'partial_outputs_retained':True})
        raise
    finally:
        if client:client.close()

if __name__=='__main__':main()
