import unittest
from mneme_asterion.state.projection import finalize
from mneme_asterion.state.ownership import own_query
class Tests(unittest.TestCase):
 def raw(self,i,body):return {'id':i,'role':'user','speaker':'user','body':body,'text':body,'source_ids':[i]}
 def test_ambiguous_owner_without_control_preserves_p2(self):
  for q in ["What is Alice's project color?","What is their project color?","Imagine my project color changes, what happens?"]:
   evidence=[{'id':'x','text':'retained evidence'}];self.assertEqual(finalize(q,evidence,[],{'audits':[]})[0],evidence)
 def test_owner_projection_and_independent_access(self):
  raw=[self.raw('old','My project color is RED.'),self.raw('c','Please forget my project color.'),self.raw('other',"My colleague's project color is BLUE.")]
  audit={'audits':[{'id':'c','operative':True,'subject':'User','attribute_quote':'my project color','restored_by':[]}]};ev=[{'id':'x','text':"My project color is RED. My colleague's project color is BLUE."}]
  out,tr=finalize('What is my project color?',ev,raw,audit);self.assertGreater(tr['cards'],0);self.assertNotIn('RED',str(out));self.assertNotIn('BLUE',str(out))
  other,_=finalize("What is my colleague's project color?",ev,raw,audit);self.assertIn('BLUE',str(other));self.assertNotIn('RED',str(other));self.assertEqual(len(raw),3);self.assertIn('RED',ev[0]['text'])
 def test_unrelated_query_preserves_p2(self):
  raw=[self.raw('c','Please forget my project color.')];evidence=[{'id':'e','text':'My office address is retained.'}]
  self.assertEqual(finalize('What is my office address?',evidence,raw,{'audits':[]})[0],evidence)
if __name__=='__main__':unittest.main()
