"""Literal quote/fragment identity reconciliation; never substitutes unrelated text."""
from mneme_asterion.retrieval.planning import *

def reconcile_quotes(v,candidates):
 assert isinstance(v,dict) and isinstance(v.get('supports'),list)
 by={r['id']:r for r in candidates};out=[];repairs=[];dropped=[];seen=set()
 for s in v['supports']:
  if not isinstance(s,dict):dropped.append({'reason':'not_object'});continue
  q=s.get('quote');ident=s.get('source_id');chosen=None
  if not isinstance(q,str) or not q.strip():dropped.append({'proposal':s,'reason':'empty_quote'});continue
  if ident in by and q in by[ident]['body']:chosen=by[ident]
  else:
   exact=[r for r in candidates if q in r['body']]
   named=[r for r in exact if ident in r.get('source_ids',[])]
   if len(named)==1:chosen=named[0]
   elif len(exact)==1:chosen=exact[0]
   else:dropped.append({'proposal':s,'reason':'ambiguous_exact_quote' if exact else 'quote_not_in_any_candidate'});continue
   repairs.append({'proposed_id':ident,'actual_fragment_id':chosen['id'],'actual_source_ids':chosen['source_ids'],'quote_sha256':hashlib.sha256(q.encode()).hexdigest(),'basis':'unique literal candidate body match; no reference/score used'})
  if chosen['id'] in seen:dropped.append({'proposal':s,'reason':'duplicate_fragment'});continue
  if len(out)>=3:dropped.append({'proposal':s,'reason':'support_limit'});continue
  seen.add(chosen['id']);out.append({**s,'source_id':chosen['id']})
 return {**v,'supports':out,'literal_identity_repair':{'repairs':repairs,'dropped':dropped,'policy':'provided-valid-ID-plus-exact-quote OR unique literal quote match; never replace quote with arbitrary body'}}

def generate_r1q(question,base,raw,call,tok):
 from memory_benchmark.pipeline.context import pack
 context,_=pack(normalize(base,100),tok,4096)
 plan=call(PLAN_PROMPT+'\n'+json.dumps({'QUESTION':question,'ACTUAL_BASE_CONTEXT':context},ensure_ascii=False),'R1_E_plan',validate_plan)
 trace={'version':'P1-R1Q','plan':plan,'planner_policy':'original_E;4096','base_unchanged':True,'support_budget':600,'support_limit':3}
 if not plan['needed']:return list(base),{**trace,'no_gap_parity':True}
 personal=[r for r in raw if is_personal_record(r)];idx=Lexical(personal);hits=[]
 for j,q in enumerate([question]+[q for q in plan['queries'] if q.strip()]):hits+=idx.search(q,24 if j==0 else 12)
 candidates=fit(neighbors(personal,hits),tok.count,24000);payload={'QUESTION':question,'BASE_CONTEXT':context,'CANDIDATES':candidates}
 def valid(v):
  resolved=reconcile_quotes(v,candidates)
  assert not resolved['literal_identity_repair']['dropped'],'literal quote not fully resolvable'
  scope_check(resolved,candidates,question,context)
 def recover(v):
  v=reconcile_quotes(v,candidates)
  scope=v.get('scope',{}) if isinstance(v.get('scope'),dict) else {}
  if not isinstance(scope.get('subject_quote'),str) or not scope['subject_quote'].strip() or scope['subject_quote'] not in question+'\n'+context:scope['subject_quote']=question
  if not isinstance(scope.get('requested_relation'),str) or not scope['requested_relation'].strip():scope['requested_relation']='Unresolved requested relation'
  if scope.get('operation') not in {'fact','list','count','comparison','duration','time','other'}:scope['operation']='other'
  v['scope']=scope;v['supports']=[{**s,'purpose':s.get('purpose') if s.get('purpose') in {'premise','bridge','list_member','highlight'} else 'premise','reason':s.get('reason') if isinstance(s.get('reason'),str) and len(s['reason'].strip())>=8 else 'Literal quote resolved; semantic relevance remains uncertain.'} for s in v['supports']]
  scope_check(v,candidates,question,context);return v
 valid.recover=recover
 raw_decision=call(SCOPE_SELECT+'\n'+json.dumps(payload,ensure_ascii=False),'R1Q_scope_select',valid)
 decision=recover(raw_decision);supports,dropped=build_supports(decision,candidates,tok.count)
 trace.update(candidates=[x['id'] for x in candidates],raw_decision=raw_decision,decision=decision,budget_dropped=dropped,selected=[x['id'] for x in supports],personal_pool=len(personal),all_raw=len(raw),literal_query_included=True)
 return compose(base,supports),trace
