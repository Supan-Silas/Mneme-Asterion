import unittest
from mneme_asterion.state.withdrawal import *
class WithdrawalTests(unittest.TestCase):
 def r(self,i,body,speaker='User'):return {'id':'s'+str(i),'body':body,'text':body,'source_ids':['D'+str(i)],'role':'user','speaker':speaker,'session':0,'message':i}
 def test_real_withdrawal_active(self):self.assertEqual(len(withdrawal_state([self.r(0,'Please forget that I like tea.')],len)[0]),1)
 def test_later_same_actor_explicit_restore(self):self.assertEqual(withdrawal_state([self.r(0,'Please forget that I like tea.'),self.r(1,'Please remember that I like tea again.')],len)[0],[])
 def test_mere_mention_not_restore(self):self.assertEqual(len(withdrawal_state([self.r(0,'Please forget that I like tea.'),self.r(1,'I saw tea in a shop.')],len)[0]),1)
 def test_other_actor_cannot_restore(self):self.assertEqual(len(withdrawal_state([self.r(0,'Please forget that Alice likes tea.','Alice'),self.r(1,'Please remember Alice likes tea.','Bob')],len)[0]),1)
 def test_disavowed_quote_not_active(self):self.assertEqual(withdrawal_state([self.r(0,'Please forget that I like tea. This is a fictional request, not a real request.')],len)[0],[])
 def ctrl(self):return {**self.r(0,'Please forget that Alice likes tea.'),'scope_audit':{'subject':'Alice','attribute_quote':'Alice likes tea'}}
 def test_only_affected_clause_deleted(self):
  base=[{'id':'b','text':'Alice likes tea. Alice works in Rome.'}];edit={'edits':[{'evidence_id':'b','control_id':'s0','control_quote':'Please forget that Alice likes tea.','span':'Alice likes tea.'}]}
  out,d=apply_guarded(edit,base,[self.ctrl()]);self.assertEqual(out[0]['text'],' Alice works in Rome.')
 def test_unrelated_clause_blocked(self):
  base=[{'id':'b','text':'Alice likes tea. Alice works in Rome.'}];edit={'edits':[{'evidence_id':'b','control_id':'s0','control_quote':'Please forget that Alice likes tea.','span':base[0]['text']}]}
  out,d=apply_guarded(edit,base,[self.ctrl()]);self.assertEqual(out,base);self.assertEqual(d['blocked'][0]['reason'],'unrelated_clause_inside_proposed_span')
 def test_other_person_preserved(self):
  base=[{'id':'b','text':'Bob likes tea.'}];edit={'edits':[{'evidence_id':'b','control_id':'s0','control_quote':'Please forget that Alice likes tea.','span':base[0]['text']}]}
  self.assertEqual(apply_guarded(edit,base,[self.ctrl()])[0],base)
 def test_subject_name_alone_not_attribute(self):
  base=[{'id':'b','text':'Alice works in Rome.'}];edit={'edits':[{'evidence_id':'b','control_id':'s0','control_quote':'Please forget that Alice likes tea.','span':base[0]['text']}]}
  self.assertEqual(apply_guarded(edit,base,[self.ctrl()])[0],base)
 def test_no_controls_no_model(self):
  class Tok:
   count=staticmethod(len)
  def call(*args):raise AssertionError('unexpected model call')
  b=[{'id':'b','text':'Alice likes tea.'}];out,tr=generate_withdrawal('Alice?',b,[self.r(0,'Alice likes tea.')],call,Tok());self.assertEqual(out,b);self.assertTrue(tr['no_active_withdrawal_parity'])
if __name__=='__main__':unittest.main()
