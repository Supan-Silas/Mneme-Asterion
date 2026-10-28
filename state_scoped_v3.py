"""Query-local state projection. No persisted source deletion. Ambiguous multi-slot queries preserve P2."""
import re
from state_finalize_v6 import finalize as state_finalize,terms
from state_scoped_v1 import finalize as prior_finalize,own_query
def focus(question):return re.split(r'\bReply\b',question,flags=re.I)[0].strip()
def single(question):return not re.search(r'\b(?:and|also|both|compare|versus|all|list|each|respectively|before|previous|ever)\b',focus(question),re.I)
def finalize(question,evidence,raw,audit):
 if not single(question):return list(evidence),{'scoped_parity':True,'cards':0,'scope':'Ambiguous, compound or historical query preserves P2'}
 q=focus(question);alias=bool(re.search(r'\b(?:belongs?|assigned)\s+to\s+me\b',q,re.I)) and not re.search(r'\b(?:colleague|friend|their|his|her|someone)\b',q,re.I)
 colleague=re.fullmatch(r"What is my colleague['’]s (.+?)\?",q,re.I)
 if not(own_query(question) or alias or colleague):return list(evidence),{'cards':0,'scoped_parity':True,'scope':'Explicit single owner/attribute required'}
 out,tr=state_finalize(question,evidence,raw,audit)
 active=[s for s in tr['states'] if s['active_withdrawal'] and terms(s['attribute'])<=terms(question)]
 if colleague and active:
  attribute=colleague.group(1)
  # Only an explicit present-tense first-party declaration of the colleague's attribute.
  pattern=r"\s*My colleague['’]s "+re.escape(attribute)+r'\s+is\s+[^.!?\n]+[.]?\s*'
  records=[x for x in raw if x.get('role')=='user' and re.fullmatch(pattern,x['body'],re.I)]
  if records:
   source=records[-1]
   return [{'id':'state-owner:'+source['id'],'text':'[Exact source fact; owner: colleague. The current user withdrawal concerns their own value and does not revoke this colleague fact.]\n'+source['text'],'source_ids':source.get('source_ids',[]),'metadata':{'query_local_projection':True}}],{**tr,'cards':1,'scoped_parity':False,'projection':'explicit other owner','source_id':source['id']}
  return list(evidence),{'cards':0,'scoped_parity':True,'scope':'No exact colleague declaration; preserve P2'}
 if colleague:return list(evidence),{'cards':0,'scoped_parity':True,'scope':'No relevant withdrawal; preserve P2'}
 if len(active)==1:
  state=active[0];source=next(x for x in raw if x['id']==state['control_id'])
  text='[Source-backed memory control record: withdrawn]\nThe following source withdrew the current user attribute addressed by this question. No current-user value is authorized for that exact attribute. This is a memory state, not an attribute value. Other attributes and other people cannot supply its value.\nWithdrawal source: '+source['text']
  return [{'id':'query-state:'+source['id'],'text':text,'source_ids':source.get('source_ids',[]),'metadata':{'query_local_projection':True,'attribute':state['attribute']}}],{**tr,'scoped_parity':False,'projection':'one withdrawn owner/attribute; stored sources retained'}
 if alias and tr['cards']:return out,{**tr,'scoped_parity':False,'projection':'explicit belongs-to-me alias; source-backed restored state'}
 return prior_finalize(question,evidence,raw,audit)
