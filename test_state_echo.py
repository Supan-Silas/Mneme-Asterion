import unittest
from state_withdrawal_v2 import *
class EchoTests(unittest.TestCase):
 def ctrl(self):return {'id':'c','body':'Please forget that I like coffee.','scope_audit':{'attribute_quote':'that I like coffee','subject':'User'}}
 def test_directive_only_removed(self):
  out,ch=suppress_control_echoes([{'id':'x','text':'User: Please forget that I like coffee. I enjoy books.'}],[self.ctrl()]);self.assertNotIn('like coffee',out[0]['text']);self.assertIn('I enjoy books',out[0]['text'])
 def test_ack_removed_general_advice_preserved(self):
  out,ch=suppress_control_echoes([{'id':'x','text':"Got it — I’ll forget that you like coffee.\n\nCoffee is a beverage. You can boil water."}],[self.ctrl()]);self.assertNotIn('you like coffee',out[0]['text']);self.assertIn('Coffee is a beverage',out[0]['text'])
 def test_other_person_ack_not_removed(self):
  b=[{'id':'x','text':"Got it, I'll forget Bob likes coffee."}];self.assertEqual(suppress_control_echoes(b,[self.ctrl()])[0],b)
 def test_no_active_control_parity(self):
  b=[{'id':'x','text':'Coffee is a beverage.'}];self.assertEqual(suppress_control_echoes(b,[])[0],b)
if __name__=='__main__':unittest.main()
