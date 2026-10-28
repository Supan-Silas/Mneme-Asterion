"""P2-W2: semantic clause suppression plus deterministic active-control echo removal."""
from state_withdrawal import *

ACK=re.compile(r"(?:got it|understood|i(?:['’]ll| will)|i (?:have|will)).{0,90}?(?:forget|won['’]t remember|will not remember)",re.I|re.S)

def suppress_control_echoes(base,active):
 out=[];changes=[]
 for item in base:
  text=item['text']
  for c in active:
   # A direct active control is itself a restatement of the withdrawn attribute.
   # Remove exactly its source body, not neighboring sentences or topic knowledge.
   if c['body'] and c['body'] in text:
    text=text.replace(c['body'],'');changes.append({'id':item['id'],'control_id':c['id'],'kind':'literal_active_control_body','span':c['body']})
   a=c['scope_audit'];subject=a['subject'];topic=attribute_terms(a['attribute_quote'])-set(terms(subject))
   # An acknowledgement may echo the same attribute with I->you. Only inspect
   # literal acknowledgement sentences; ordinary coffee/dance knowledge remains.
   spans=[]
   for m in ACK.finditer(text):
    start=m.start();tail=text[m.end():];endmatch=re.search(r'[.!?](?=\s|$)|\n',tail);end=m.end()+endmatch.end() if endmatch else len(text);span=text[start:end]
    named=subject.casefold() not in {'user','the user','i','me'}
    owner_ok=subject.casefold() in span.casefold() if named else bool(re.search(r'\byou(?:r)?\b',span,re.I))
    if topic&attribute_terms(span) and owner_ok:spans.append(span)
   for span in sorted(set(spans),key=len,reverse=True):
    if span in text:text=text.replace(span,'');changes.append({'id':item['id'],'control_id':c['id'],'kind':'literal_acknowledgement_echo','span':span})
  if text.strip():out.append({**item,'text':text})
 return out,changes

def generate_withdrawal_v2(question,base,raw,call,tok):
 ev,tr=generate_withdrawal(question,base,raw,call,tok);active,audit=withdrawal_state(raw,tok.count);ev,changes=suppress_control_echoes(ev,active)
 return ev,{**tr,'version':'P2-W2','deterministic_control_echo_suppression':changes,'echo_policy':'exact active control bodies + exact acknowledgement sentences about same attribute/owner; generic knowledge retained'}
