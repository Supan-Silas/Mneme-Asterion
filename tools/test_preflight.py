import unittest
from tools.preflight import check_values


class ReleaseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.values = dict(P2_SCOPED_STATE='1', AMI_LLM_MODEL='gpt-4o-mini',
            AMI_EMBED_MODEL='text-embedding-v4', AMI_EMBED_BACKEND='openai',
            AMI_AUTH_SCHEME='bearer', AMI_AUTH_TOKEN='synthetic-not-a-secret',
            OPENAI_API_KEY='fixture', OPENAI_BASE_URL='https://example.invalid/v1',
            AMI_EMBED_API_KEY='fixture', AMI_EMBED_BASE_URL='https://example.invalid/v1')

    def test_verified_profile(self):
        self.assertEqual([], check_values(self.values))

    def test_p2_rejected(self):
        self.values['P2_SCOPED_STATE'] = '0'
        self.assertTrue(check_values(self.values))

    def test_implicit_method_rejected(self):
        self.values.pop('P2_SCOPED_STATE')
        self.assertTrue(check_values(self.values))

    def test_no_auth_rejected(self):
        self.values['AMI_AUTH_SCHEME'] = 'none'
        self.assertTrue(check_values(self.values))

    def test_wrong_model_rejected(self):
        self.values['AMI_LLM_MODEL'] = 'different-model'
        self.assertTrue(check_values(self.values))

    def test_empty_secret_rejected_without_echo(self):
        self.values['AMI_AUTH_TOKEN'] = ' '
        errors = check_values(self.values)
        self.assertTrue(errors)
        self.assertNotIn('fixture', str(errors))


if __name__ == '__main__':
    unittest.main()
