import unittest
from state_policy import *
class NoticeTests(unittest.TestCase):
 def active(self):return [{'id':'c','body':'Please forget I like coffee.','scope_audit':{'subject':'User'}}]
 def test_notice_value_free(self):self.assertNotIn('coffee',NOTICE.casefold());self.assertNotIn('hora',NOTICE.casefold())
 def test_no_relevance_parity(self):
  b=[{'id':'b','text':'User likes novels.'}];self.assertEqual(apply_notice(b,{'relevant_control_ids':[],'reason':'different attribute'},self.active()),b)
 def test_all_original_text_and_ids_preserved(self):
  b=[{'id':'b','text':'User likes novels.','metadata':{}},{'id':'c2','text':'User has a dog.'}];v=apply_notice(b,{'relevant_control_ids':['c'],'reason':'direct'},self.active());self.assertTrue(v[0]['text'].endswith(b[0]['text']));self.assertEqual([e['id'] for e in v],['b','c2']);self.assertEqual(v[1],b[1])
 def test_unknown_control_rejected(self):
  with self.assertRaises(AssertionError):relevant_check({'relevant_control_ids':['invented'],'reason':'invalid'},self.active())
if __name__=='__main__':unittest.main()
