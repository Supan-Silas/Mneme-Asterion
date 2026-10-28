"""Two explicit current-user attributes: preserve a valid slot while honoring another slot's withdrawal."""
import re
from mneme_asterion.state.scope import finalize as prior,focus
from mneme_asterion.state.transitions import finalize as states,terms
def finalize(question,evidence,raw,audit):
 q=focus(question);m=re.fullmatch(r'What (?:are|is) (my .+?) and (my .+?)\?',q,re.I)
 if not m:return prior(question,evidence,raw,audit)
 attributes=[m.group(1),m.group(2)]
 if any(re.search(r"\b(?:colleague|friend|their|his|her|before|previous|ever)\b|['’]",s,re.I) for s in attributes):return prior(question,evidence,raw,audit)
 _,tr=states(question,evidence,raw,audit)
 matching=[[s for s in tr['states'] if terms(s['attribute'])==terms(attribute)] for attribute in attributes]
 if not any(any(s['active_withdrawal'] for s in slot) for slot in matching):return prior(question,evidence,raw,audit)
 rows=[]
 for attribute,slot in zip(attributes,matching):
  active=[s for s in slot if s['active_withdrawal']]
  if len(active)==1:
   src=next(x for x in raw if x['id']==active[0]['control_id']);text='[Source-backed memory control record: withdrawn; exact attribute '+attribute+']\nNo current-user value is authorized for this exact attribute. This is a state, not an attribute value.\n'+src['text']
  elif active:return prior(question,evidence,raw,audit)
  else:
   found=[]
   for src in raw:
    if src.get('role')!='user':continue
    for clause in re.split(r';|\n',src['body']):
     if re.fullmatch(r'\s*'+re.escape(attribute)+r'\s+is\s+(?:now\s+)?[^.!?;\n]+[.]?\s*',clause,re.I):found.append((src,clause.strip()))
   if not found:return prior(question,evidence,raw,audit)
   src,quote=found[-1];text='[Literal current-user declaration; exact attribute '+attribute+']\n'+quote
  rows.append({'id':'query-slot:'+src['id']+':'+str(len(rows)),'text':text,'source_ids':src.get('source_ids',[]),'metadata':{'query_local_projection':True,'attribute':attribute}})
 return rows,{**tr,'scoped_parity':False,'cards':len(rows),'projection':'two exact current-user slots; unrelated valid declaration retained; no database mutation'}
