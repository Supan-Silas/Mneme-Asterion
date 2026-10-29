import json,unittest
from mneme_asterion.availability import literal_fallback
from mneme_asterion.state.withdrawal import withdrawal_state,generate_withdrawal
from mneme_asterion.state.policy import add_policy_notice
class Tok:
 count=staticmethod(lambda s:len(s.split()))
class Chars:
 count=staticmethod(len)
def record(i,body,role='user'):
 return {'id':str(i),'body':body,'text':body,'role':role,'speaker':'User' if role=='user' else 'Assistant','source_ids':[str(i)],'source_time':'2026-10-29'}
class Tests(unittest.TestCase):
 def test_tail_and_provenance(self):
  raw=[record(0,'filler '*300+'zirconium is the selected metal.','assistant')]
  out=literal_fallback('zirconium',[],raw,Tok())[0]
  head,body=out['text'].split('\n',1)
  self.assertIn('zirconium',body);self.assertIn(body,raw[0]['body']);self.assertLessEqual(Tok.count(body),200)
  self.assertIn('Assistant',head);self.assertIn('2026-10-29',head)
 def test_no_match_base_parity(self):
  base=[{'id':'b','text':'retained'}]
  self.assertEqual(literal_fallback('zirconium',base,[record(0,'tea')],Tok()),base)
 def controls(self):return [record(i,'Please forget my attribute'+str(i)+'. '+('padding '*100)) for i in range(25)]
 def test_all_controls_and_late_restore(self):
  raw=self.controls();active,audit=withdrawal_state(raw,len)
  self.assertEqual(len(active),25);self.assertEqual(audit['omitted_controls'],0)
  raw.append(record(25,'Please remember my attribute24 again.'))
  active,_=withdrawal_state(raw,len);self.assertNotIn('24',[c['id'] for c in active])
 def test_filter_batches_cover_all(self):
  seen=[]
  def call(prompt,stage,valid):
   p=json.loads(prompt.rsplit('\n',1)[1]);seen.extend(c['id'] for c in p['POSSIBLE_CONTROL_SOURCES'])
   v={'edits':[],'unresolved':[]};valid(v);return v
  base=[{'id':'b','text':'unrelated valid fact'}]
  out,_=generate_withdrawal('question',base,self.controls(),call,Chars())
  self.assertEqual(out,base);self.assertEqual(set(seen),{str(i) for i in range(25)})
 def test_notice_late_control(self):
  def call(prompt,stage,valid):
   p=json.loads(prompt.rsplit('\n',1)[1]);ids=[c['id'] for c in p['ACTIVE_SOURCE_CONTROLS']]
   v={'relevant_control_ids':['24'] if '24' in ids else [],'reason':'fixture'};valid(v);return v
  out,_=add_policy_notice('attribute24',[],self.controls(),call,Chars())
  self.assertEqual(out[0]['id'],'memory-status')
