import unittest
from repair_quotes import reconcile_quotes
class IdentityTests(unittest.TestCase):
 def setUp(self):self.cs=[{'id':'s1','source_ids':['D1:1'],'body':'Her name is Shadow.'},{'id':'s2','source_ids':['D1:2'],'body':'That sounds nice.'}]
 def test_original_source_alias(self):self.assertEqual(reconcile_quotes({'supports':[{'source_id':'D1:1','quote':'Her name is Shadow.'}]},self.cs)['supports'][0]['source_id'],'s1')
 def test_wrong_existing_id_correct_literal_quote(self):self.assertEqual(reconcile_quotes({'supports':[{'source_id':'s2','quote':'Her name is Shadow.'}]},self.cs)['supports'][0]['source_id'],'s1')
 def test_paraphrase_dropped_not_replaced(self):self.assertEqual(reconcile_quotes({'supports':[{'source_id':'s1','quote':'The puppy is called Shadow.'}]},self.cs)['supports'],[])
 def test_unrelated_body_never_substituted(self):self.assertEqual(reconcile_quotes({'supports':[{'source_id':'s2','quote':'Imaginary fact'}]},self.cs)['supports'],[])
 def test_ambiguous_unknown_id_dropped(self):self.assertEqual(reconcile_quotes({'supports':[{'source_id':'unknown','quote':'Her name is Shadow.'}]},self.cs+[{'id':'s3','source_ids':['D2:1'],'body':'Her name is Shadow.'}])['supports'],[])
 def test_duplicate_not_counted_twice(self):self.assertEqual(len(reconcile_quotes({'supports':[{'source_id':'s1','quote':'Her name is Shadow.'},{'source_id':'D1:1','quote':'Shadow'}]},self.cs)['supports']),1)
 def test_named_source_disambiguates(self):self.assertEqual(reconcile_quotes({'supports':[{'source_id':'D1:1','quote':'Her name is Shadow.'}]},self.cs+[{'id':'s3','source_ids':['D2:1'],'body':'Her name is Shadow.'}])['supports'][0]['source_id'],'s1')
if __name__=='__main__':unittest.main()
