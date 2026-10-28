import unittest
from state_projection_v4 import finalize
def raw(body,i):return {'id':str(i),'role':'user','speaker':'user','body':body,'text':body,'source_ids':[str(i)]}
class Check(unittest.TestCase):
 def test_pair(self):
  r=[raw('My Cedar access tag is X1; my Cedar delivery tag is X2.',0),raw('Please remove my Cedar access tag from memory.',1)]
  ev,tr=finalize('What are my Cedar access tag and my Cedar delivery tag?',[],r,{'audits':[]})
  text=' '.join(x['text'] for x in ev);self.assertNotIn('X1',text);self.assertIn('X2',text);self.assertEqual(len(ev),2);self.assertEqual(len(r),2)
 def test_reverse(self):
  r=[raw('My Cedar access tag is X1; my Cedar delivery tag is X2.',0),raw('Please remove my Cedar access tag from memory.',1)]
  ev,tr=finalize('What are my Cedar delivery tag and my Cedar access tag?',[],r,{'audits':[]});self.assertIn('X2',ev[0]['text']);self.assertNotIn('X1',' '.join(x['text'] for x in ev))
 def test_no_exact_other_fact(self):
  ev=[{'id':'e','text':'Unchanged','source_ids':[]}];r=[raw('Please remove my Cedar access tag from memory.',1)]
  self.assertEqual(finalize('What are my Cedar access tag and my Cedar address?',ev,r,{'audits':[]})[0],ev)
if __name__=='__main__':unittest.main()
