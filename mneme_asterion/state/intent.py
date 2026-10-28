"""Bounded explicit memory-control grammar; no model calls or source rewrites."""
import re
from copy import deepcopy

_PATTERNS=[
 r'(?:please\s+)?(?:remove|delete|erase)\s+(?P<scope>my\s+.+?)\s+from\s+(?:(?:your|the)\s+)?memory',
 r'I\s+no\s+longer\s+want\s+you\s+to\s+remember\s+(?P<scope>my\s+.+?)',
 r'(?:please\s+)?stop\s+remembering\s+(?P<scope>my\s+.+?)',
]
_EXCLUDED=re.compile(r'\b(?:if|unless|would|could|might|hypothetical|fictional|quoted|imagine|friend|colleague|someone|example|but|except|and|or)\b|[\n?!;:"“”]',re.I)
def explicit_withdrawal(record):
 if record.get('role')!='user' or record.get('speaker','').casefold() not in {'user','i','me','human'}:return None
 body=record.get('body','').strip()
 if _EXCLUDED.search(body):return None
 text=body[:-1].rstrip() if body.endswith('.') else body
 for pattern in _PATTERNS:
  match=re.fullmatch(pattern,text,re.I)
  if not match:continue
  scope=match.group('scope')
  # Literal nominal slots only. Do not widen this patch into arbitrary prose.
  words=re.findall(r'[A-Za-z]+',scope)
  if not 3<=len(words)<=10 or re.search(r"['’]|\b(?:is|was|like|likes|prefer|has|have)\b",scope,re.I):return None
  return scope
 return None

def augment_audit(raw,original):
 result=deepcopy(original);audits=result.setdefault('audits',[]);existing={x['id'] for x in audits}
 added=[]
 for pos,record in enumerate(raw):
  scope=explicit_withdrawal(record)
  if not scope or record['id'] in existing:continue
  restored=[]
  for later in raw[pos+1:]:
   if later.get('role')!='user' or later.get('speaker')!=record.get('speaker'):continue
   body=later.get('body','').strip()
   # Require direct reauthorization of the SAME literal slot. Broader lexical
   # matching remains the pre-existing detector's responsibility.
   pat=r'(?:please\s+)?remember\s+'+re.escape(scope)+r'\s+again(?:\s*:\s*[^?\n]+|[.!]?)'
   if re.fullmatch(pat,body,re.I):restored.append(later['id'])
  audits.append({'id':record['id'],'operative':True,'active':not restored,'subject':'User','attribute_quote':scope,'restored_by':restored,'reason':'Exact explicit memory-control grammar; literal scope retained','state_policy':'bounded-intent-v5'})
  added.append(record['id'])
 result['intent_v5_added_ids']=added
 return result
