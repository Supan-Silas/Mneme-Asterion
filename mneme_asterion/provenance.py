"""Read-only, exact request provenance for native evidence.

Request origin identifies an ingestion interval, NOT a fact's exact supporting
sentence. A request spanning a control boundary must remain ambiguous.
"""
import sqlite3,json
from contextlib import closing
from pathlib import Path

def request_source_map(dbpath, raw, user_id=None):
 known={s for r in raw for s in r.get('source_ids',[])}
 with closing(sqlite3.connect(Path(dbpath).resolve().as_uri()+'?mode=ro',uri=True)) as db:
  users=[r[0] for r in db.execute('SELECT DISTINCT user_id FROM e_raw_requests')]
  if user_id is None:
   if len(users)!=1:raise ValueError('Expected exactly one isolated history/user')
   uid=users[0]
  else:
   if user_id not in users:raise ValueError('Explicit user does not exist')
   uid=user_id
  requests={}
  for rid,payload in db.execute('SELECT request_id,payload FROM e_raw_requests WHERE user_id=?',(uid,)):
   p=json.loads(payload)
   ids=[m.get('source_id') or f'{rid}:{i}' for i,m in enumerate(p['messages'])]
   if ids and all(s in known for s in ids):requests[rid]=list(dict.fromkeys(ids))
  return {ident:requests[rid] for ident,rid in db.execute('SELECT id,request_id FROM items WHERE user_id=?',(uid,)) if rid in requests}

def attach(evidence,mapping):
 out=[];attached=0
 for e in evidence:
  if e.get('source_ids') or e['id'] not in mapping:out.append(e);continue
  out.append({**e,'source_ids':mapping[e['id']], 'metadata':{**e.get('metadata',{}),'provenance_granularity':'request','provenance_resolution':'exact item.id -> request_id -> payload message source_id; not exact sentence attribution'}})
  attached+=1
 return out,{'attached':attached,'unresolved':sum(not e.get('source_ids') for e in out)}
