"""P2-W: narrow read-time suppression of explicit active withdrawals.
No reference/category/score inputs; no database deletion or new value updates.
"""
from mneme_asterion.retrieval.support import *
from mneme_asterion.retrieval.quotes import reconcile_quotes
from e_core.methods import WITHDRAW,RESTORE,audit_controls,attribute_terms,FILTER_PROMPT,validate_edits

def withdrawal_state(raw,count):
 personal=lambda r:r['role']=='user' or r['speaker'].strip().casefold() not in {'assistant','ai','chatgpt','system',''}
 controls=[r for r in raw if personal(r) and WITHDRAW.search(r['body'].strip())]
 shown=controls;positions={r['id']:i for i,r in enumerate(raw)};active=[];audits=[]
 for c in shown:
  later=[r for r in raw[positions[c['id']]+1:] if personal(r) and r['speaker'].strip().casefold()==c['speaker'].strip().casefold() and RESTORE.search(r['body'])]
  a=audit_controls([c],later,None)['controls'][0]
  if a['subject']=='User' and c['speaker'].strip().casefold() not in {'user','i','me','human'}:a['subject']=c['speaker']
  audits.append(a)
  if a['active']:active.append({**c,'scope_audit':a})
 return active,{'candidate_controls':len(controls),'shown_controls':len(shown),'omitted_controls':len(controls)-len(shown),'audits':audits,'policy':'anchored literal withdrawal; real disavowal and same-actor later explicit restoration; not a general semantic state resolver'}

def normalize_edits(v,base,controls):
 assert isinstance(v,dict) and isinstance(v.get('edits'),list)
 out=[];repairs=[];dropped=[];by={e['id']:e for e in base};cs={c['id']:c for c in controls}
 for old in v['edits']:
  if not isinstance(old,dict):dropped.append({'reason':'not_object'});continue
  e=dict(old);span=e.get('span');cq=e.get('control_quote')
  if not isinstance(span,str) or not span.strip() or not isinstance(cq,str) or not cq.strip():dropped.append({'proposal':old,'reason':'empty_literal'});continue
  if e.get('evidence_id') not in by or span not in by[e['evidence_id']]['text']:
   matches=[x for x in base if span in x['text']]
   if len(matches)!=1:dropped.append({'proposal':old,'reason':'nonunique_or_missing_literal_span'});continue
   repairs.append({'field':'evidence_id','old':e.get('evidence_id'),'new':matches[0]['id']});e['evidence_id']=matches[0]['id']
  if e.get('control_id') not in cs or cq not in cs[e['control_id']]['body']:
   matches=[x for x in controls if cq in x['body']]
   if len(matches)!=1:dropped.append({'proposal':old,'reason':'nonunique_or_missing_control_quote'});continue
   repairs.append({'field':'control_id','old':e.get('control_id'),'new':matches[0]['id']});e['control_id']=matches[0]['id']
  out.append(e)
 return {**v,'edits':out,'identity_repairs':repairs,'dropped_nonliteral':dropped}

def apply_guarded(v,base,controls):
 v=normalize_edits(v,base,controls);validate_edits(v,base,controls);cs={c['id']:c for c in controls};accepted=[];blocked=[]
 for e in v['edits']:
  a=cs[e['control_id']]['scope_audit'];topic=attribute_terms(a['attribute_quote']);subject=a['subject'];reason=None
  if subject.casefold() not in {'user','the user','i','me'}:topic-=set(terms(subject))
  if not topic or not topic&attribute_terms(e['span']):reason='attribute_not_literally_aligned'
  elif subject.casefold() not in {'user','the user','i','me'} and subject.casefold() not in e['span'].casefold():reason='named_subject_not_in_literal_span'
  else:
   clauses=re.split(r'(?<=[.!?;])\s+|\n+|\s+\b(?:and|but|while)\b\s+',e['span'],flags=re.I)
   if any(attribute_terms(c) and not topic&attribute_terms(c) for c in clauses):reason='unrelated_clause_inside_proposed_span'
  if reason:blocked.append({'proposal':e,'reason':reason})
  else:accepted.append(e)
 out=[]
 for b in base:
  text=b['text']
  for span in sorted({e['span'] for e in accepted if e['evidence_id']==b['id']},key=len,reverse=True):text=text.replace(span,'')
  if text.strip():out.append({**b,'text':text})
 return out,{'decision':v,'accepted':accepted,'blocked':blocked,'scope':'read-time evidence suppression only; source DB unchanged'}

def edit_rejection_message(dropped,base,controls):
 bad_e={str(x.get('proposal',{}).get('evidence_id')) for x in dropped}
 bad_c={str(x.get('proposal',{}).get('control_id')) for x in dropped}
 return ('Rejected nonliteral withdrawal edits: '+json.dumps(dropped,ensure_ascii=False)+
  '\nCopy span exactly from EXISTING_EVIDENCE.text and control_quote exactly from POSSIBLE_CONTROL_SOURCES.body; preserve punctuation and line breaks. Do not invent a deletion or omit a required deletion to pass validation.'+
  '\nReferenced source data: '+json.dumps({'evidence':[{'id':e['id'],'text':e['text']} for e in base if str(e['id']) in bad_e],
  'controls':[{'id':c['id'],'body':c['body']} for c in controls if str(c['id']) in bad_c]},ensure_ascii=False))


def control_batches(active,count,budget=14000):
 batches=[];batch=[];used=0
 for c in active:
  n=count(json.dumps(c,ensure_ascii=False))
  if batch and used+n>budget:batches.append(batch);batch=[];used=0
  batch.append(c);used+=n
 if batch:batches.append(batch)
 return batches

def generate_withdrawal(question,base,raw,call,tok):
 active,audit=withdrawal_state(raw,tok.count)
 groups=control_batches(active,tok.count)
 if len(groups)<=1:return _filter_active(question,base,active,audit,call,tok)
 evidence=list(base);traces=[]
 for group in groups:
  ids={c['id'] for c in group}
  subaudit={**audit,'audits':[a for a in audit['audits'] if a['id'] in ids]}
  evidence,trace=_filter_active(question,evidence,group,subaudit,call,tok);traces.append(trace)
 return evidence,{'state_audit':audit,'control_batches':traces,'all_controls_inspected':len(active)}

def _filter_active(question,base,active,audit,call,tok):
 if not active:return list(base),{'version':'P2-W','state_audit':audit,'no_active_withdrawal_parity':True}
 batches=[];batch=[];used=0
 for e in base:
  n=tok.count(json.dumps(e,ensure_ascii=False))
  if batch and used+n>16000:batches.append(batch);batch=[];used=0
  batch.append(e);used+=n
 if batch:batches.append(batch)
 result=[];decisions=[]
 for j,batch in enumerate(batches):
  payload={'QUESTION':question,'EXISTING_EVIDENCE':batch,'POSSIBLE_CONTROL_SOURCES':active,'LATER_POSSIBLE_REAUTHORIZATION':[],'active_control_audit':audit}
  def valid(v):
   n=normalize_edits(v,batch,active)
   assert not n['dropped_nonliteral'],edit_rejection_message(n['dropped_nonliteral'],batch,active)
   validate_edits(n,batch,active)
  valid.recover=lambda v:normalize_edits(v,batch,active)
  v=call(FILTER_PROMPT+'\n'+json.dumps(payload,ensure_ascii=False),'P2W_filter_'+str(j),valid);out,d=apply_guarded(v,batch,active);result+=out;decisions.append(d)
 return result,{'version':'P2-W','state_audit':audit,'batches':decisions,'all_base_items_inspected':len(base),'updates_not_modified':True,'source_database_not_deleted':True}
