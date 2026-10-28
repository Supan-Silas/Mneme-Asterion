"""Narrow I/H2 patch: explicit query-matching state only; P2 otherwise."""
from mneme_asterion.state.transitions import finalize as full_finalize
from mneme_asterion.state.transitions import terms
import re
def own_query(question):
 return bool(re.search(r'\b(?:my|mine)\b',question,re.I)) and not re.search(r'\b(?:colleague|friend|their|his|her|someone|hypothetical|suppose|imagine)\b',question,re.I) and not re.search(r"\b(?!(?:What|Who|Where|When|How|It)['’]s\b)[A-Z][a-z]+['’]s\b",question)
def finalize(question,evidence,raw,audit):
 if not own_query(question):return list(evidence),{'cards':0,'scoped_parity':True,'scope':'Explicit current-user query required; ambiguous/other-owner queries preserve P2'}
 out,trace=full_finalize(question,evidence,raw,audit)
 if not trace['cards']:return list(evidence),{**trace,'scoped_parity':True,'scope':'Only queries directly naming the audited literal attribute; original P2 handles other questions'}
 # Retrieval partition, not deletion: other-owner values cannot fill a
 # withdrawn current-user slot. Explicit other-owner queries take the P2 path.
 edits=[];partitioned=[]
 for item in out:
  text=item['text']
  for state in trace['states']:
   scope=terms(state['attribute'])
   if not state['active_withdrawal'] or not scope<=terms(question):continue
   masked=re.sub(r'\[[^\]\n]*\]',lambda m:' '*len(m.group()),text)
   for match in re.finditer(r'[^\n.!?;]+(?:[.!?;]|$)',masked):
    chunk=re.sub(r'^\s*(?:(?:I|User|Assistant):\s*)?','',match.group())
    for part in re.split(r'\s+\b(?:and|but|while)\b\s+',chunk,flags=re.I):
     span=part.strip()
     if not span or not scope<=terms(span):continue
     other=re.search(r"\b(?:my\s+)?(?:colleague|friend|neighbor|neighbour)['’]s\b|\b(?:his|her|their)\b",span,re.I) or re.search(r"\b(?!User\b|Assistant\b)[A-Z][a-z]+['’]s\b",span)
     if other and span in text:text=text.replace(span,'');edits.append({'id':item['id'],'span':span,'reason':'other-owner attribute outside explicitly withdrawn current-user query'})
  if text.strip():partitioned.append({**item,'text':text})
 out=partitioned;trace['owner_partition_edits']=edits
 return out,{**trace,'scoped_parity':False}
