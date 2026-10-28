"""Conservative literal-scope state finalizer. Never mutates the source database.

Experimental subset: explicit first-person attributes identified by all content
words of a literal control. Ambiguous/other-person clauses are retained.
"""
import re
from mneme_asterion.state.intent import explicit_withdrawal,augment_audit
STOP=set('a an the of for my me i user please forget remember use using retain restore again now current currently to this that it is was are attribute anymore do not dont and'.split())
def terms(s):
 return {w[:-1] if w.endswith('s') and len(w)>4 else w for w in re.findall(r'[a-z]+',s.lower()) if w not in STOP}
def safe_source(r):
 # Explicit imperative subset. Do not promote a question, condition, or quote
 # into a control merely because an upstream audit marked it operative.
 if re.search(r'\b(?:if|unless|would|could|might|hypothetical|fictional|quoted|imagine|not a real request|not my request)\b|[?"“”]',r['body'],re.I):return False
 if explicit_withdrawal(r) is not None:return True
 return r.get('role')=='user' and bool(re.match(r'^\s*(?:please\s+)?(?:forget|remove|delete|erase|remember|restore)\b',r['body'],re.I)) and not re.search(r'\b(?:hypothetical|fictional|quoted|imagine|not a real request|not my request)\b',r['body'],re.I)
def owner_safe(text):
 # Do not suppress advice, other owners or quotation merely sharing topic words.
 if re.search(r'\b(?:friend|colleague|their|his|her|someone|example|fiction|hypothetical|quoted)\b',text,re.I):return False
 if re.search(r'[“”"]',text) and not re.match(r'^(?:my|our|i|user|you|your)\b',text,re.I):return False
 if re.search(r"\b[A-Z][a-z]+['’]s\b",text):return False
 if re.match(r'^(?!My\b|The\b|Your\b)[A-Z][a-z]+\s+(?:has|owns|said|uses)\b',text):return False
 if re.match(r'^(?!(?:my|the|your|user|i|you)\b)[a-z]+\s+(?:has|owns|said|uses)\b',text,re.I):return False
 return True
def finalize(question,evidence,raw,state_audit):
 state_audit=augment_audit(raw,state_audit)
 by={r['id']:r for r in raw};position={r['id']:i for i,r in enumerate(raw)}
 source_position={sid:i for i,r in enumerate(raw) for sid in [r['id'],*r.get('source_ids',[])]}
 states=[]
 for a in state_audit.get('audits',[]):
  c=by.get(a['id'])
  if not c or not a.get('operative') or not safe_source(c):continue
  if a['subject'].casefold() not in {'user','the user','i','me'}:continue
  # Never copy an attribute value into a supposedly value-free state card.
  # This prototype accepts nominal attribute names only, not "I like coffee".
  if re.search(r'\b(?:like|likes|love|loves|enjoy|enjoys|prefer|prefers|is|was|has|have|equals)\b|[0-9=:]',a['attribute_quote'],re.I):continue
  scope=terms(a['attribute_quote'])
  if len(scope)<2:continue
  # Original resolver allows one-word overlap. Require full scope in restoration.
  restores=[by[i] for i in a.get('restored_by',[]) if i in by and position[i]>position[c['id']] and safe_source(by[i]) and by[i].get('speaker')==c.get('speaker') and scope<=terms(by[i]['body'])]
  latest=max(restores,key=lambda r:position[r['id']]) if restores else None
  states.append({'scope':scope,'attribute':a['attribute_quote'],'control':c,'restore':latest,'at':position[latest['id'] if latest else c['id']]})
 # Later explicit control for the same exact literal scope determines current state.
 current={}
 for s in states:
  k=tuple(sorted(s['scope']))
  if k not in current or current[k]['at']<s['at']:current[k]=s
 changes=[];out=[]
 for item in evidence:
  text=item['text']
  speaker=re.search(r'\bspeaker\s+([^;\]\n]+)',text,re.I)
  if speaker and speaker.group(1).strip().casefold() not in {'user','i','me','human'}:
   out.append(item);continue
  # Keep source headers and unrelated clauses byte-for-byte; edit only body spans.
  for state in current.values():
   if state['restore'] is not None:
    # A live attribute must not be erased indiscriminately. Only remove a
    # provably older source. Missing provenance is unresolved, not "old".
    ids=item.get('source_ids',[])
    if not ids or any(s not in source_position for s in ids):continue
    if max(source_position[s] for s in ids)>=position[state['restore']['id']]:continue
   spans=[]
   # Mask headers before sentence splitting so semicolons inside headers
   # never become editable fragments; all offsets remain unchanged.
   masked=re.sub(r'\[[^\]\n]*\]',lambda m:' '*len(m.group()),text)
   for m in re.finditer(r'[^\n.!?;]+(?:[.!?;]|$)',masked):
    chunk=m.group(0)
    chunk=re.sub(r'^\s*(?:\[[^\]]*\]\s*)*(?:(?:I|User|Assistant):\s*)?', '',chunk)
    # Split conjunctions conservatively so unrelated facts survive.
    for part in re.split(r'\s+\b(?:and|but|while)\b\s+',chunk,flags=re.I):
     span=part.strip()
     if span and state['scope']<=terms(span) and owner_safe(span):spans.append(span)
   for span in sorted(set(spans),key=len,reverse=True):
    if span in text:
     text=text.replace(span,'');changes.append({'evidence_id':item['id'],'control_id':state['control']['id'],'span':span})
  if text.strip():out.append({**item,'text':text})
 cards=[]
 for state in current.values():
  if not state['scope']<=terms(question):continue
  c=state['control'];r=state['restore']
  if r:
   # Surface later explicit first-person updates too; do not assert that the
   # restore value stays current forever. These are source quotations.
   followups=[x for x in raw[position[r['id']]+1:] if x.get('role')=='user' and x.get('speaker')==r.get('speaker') and re.match(r'^\s*my\b[^.!?\n]*\bis\s+(?:now\s+)?[^.!?\n]+[.!]?\s*$',x['body'],re.I) and not re.search(r'\b(?:if|would|could|might|imagine|hypothetical)\b',x['body'],re.I) and state['scope']<=terms(x['body']) and owner_safe(x['body'])]
   if followups:r=followups[-1]
   text='[Memory authorization state: active; supersedes the earlier withdrawal for this attribute]\n'+r['text']
   ids=r.get('source_ids',[])
  else:
   text='[Memory authorization state: withdrawn; owner: current user; user value: unavailable]\nThe current user explicitly withdrew their OWN value for the attribute addressed by this question. A value belonging to a colleague, friend, other person or different project does not establish the current user\'s value. No current-user value is authorized by this state record.'
   ids=c.get('source_ids',[])
  cards.append({'id':'state-final:'+c['id'],'text':text,'source_ids':ids,'metadata':{'state_finalizer':True}})
 # Preserve evidence count cap by attaching cards to first retained item.
 if cards:
  prefix='\n\n'.join(c['text'] for c in cards)+'\n\n'
  if out:out[0]={**out[0],'text':prefix+out[0]['text'],'source_ids':list(dict.fromkeys([*out[0].get('source_ids',[]),*(s for card in cards for s in card['source_ids'])])),'metadata':{**out[0].get('metadata',{}),'state_card_sources':[{'id':card['id'],'source_ids':card['source_ids']} for card in cards]}}
  else:out=[{**cards[0],'text':prefix.rstrip(),'source_ids':list(dict.fromkeys(s for card in cards for s in card['source_ids']))}]
 return out,{'states':[{'attribute':s['attribute'],'active_withdrawal':s['restore'] is None,'control_id':s['control']['id'],'restore_id':s['restore']['id'] if s['restore'] else None} for s in current.values()],'edits':changes,'cards':len(cards),'scope':'literal first-person multi-word attributes only'}
