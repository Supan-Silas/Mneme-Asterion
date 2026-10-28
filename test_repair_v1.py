import unittest
from repair_v1 import *
class RepairTests(unittest.TestCase):
 def test_user_kept(self):self.assertTrue(is_personal_record({'role':'user','speaker':'User'}))
 def test_named_assistant_person_kept(self):self.assertTrue(is_personal_record({'role':'assistant','speaker':'Maria'}))
 def test_generic_assistant_excluded(self):self.assertFalse(is_personal_record({'role':'assistant','speaker':'Assistant'}))
 def test_casefold_generic_excluded(self):self.assertFalse(is_personal_record({'role':'assistant','speaker':'CHATGPT'}))
 def test_system_not_personal(self):self.assertFalse(is_personal_record({'role':'system','speaker':'system'}))
 def test_cross_subject_quote_not_invented(self):
  with self.assertRaises(AssertionError):scope_check({'scope':{'subject_quote':'Bob','requested_relation':'name','operation':'fact'},'supports':[]},[],'Alice name?','Alice')
 def test_literal_quote_required(self):
  with self.assertRaises(ValueError):scope_check({'scope':{'subject_quote':'Alice','requested_relation':'name','operation':'fact'},'supports':[{'source_id':'s','quote':'invented','purpose':'premise','reason':'source evidence'}]},[{'id':'s','body':'actual'}],'Alice?','')
 def test_empty_support_allowed(self):scope_check({'scope':{'subject_quote':'Alice','requested_relation':'name','operation':'fact'},'supports':[]},[],'Alice name?','')
 def test_sufficient_returns_unchanged(self):
  base=[{'id':'b','text':'Alice has tea','source_ids':[],'timestamp':None,'metadata':{}}]
  class Tok:
   name='test_word_counter'
   def count(self,s):return len(s.split())
  def call(prompt,stage,valid):
   self.assertEqual(stage,'R1_E_plan');v={'needed':False,'queries':[]};valid(v);return v
  out,tr=generate_r1('What does Alice have?',base,[],call,Tok());self.assertEqual(out,base);self.assertTrue(tr['no_gap_parity'])
if __name__=='__main__':unittest.main()
