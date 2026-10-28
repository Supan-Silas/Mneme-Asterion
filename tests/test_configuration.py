import unittest
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from tools.preflight import check_values
from tools.preflight import check_file
from tools.verify_release import verify


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

    def make_tree(self, root):
        (root / 'provenance').mkdir()
        (root / 'core.py').write_text('value = 1\n', encoding='utf-8')
        digest = hashlib.sha256((root / 'core.py').read_bytes()).hexdigest()
        (root / 'provenance/CORE_SHA256.json').write_text(json.dumps({'core.py': digest}))
        (root / '.env').write_text('\n'.join(k + '=' + v for k, v in self.values.items()))
        (root / 'data').mkdir()
        (root / 'data/memory.sqlite3').write_bytes(b'existing-local-database-fixture')

    def test_existing_env_and_database_allow_repeated_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(root)
            before = (root / 'data/memory.sqlite3').read_bytes()
            with patch('tools.preflight.verify', side_effect=lambda: verify(root)):
                self.assertTrue(check_file(root / '.env')['passed'])
                self.assertTrue(check_file(root / '.env')['passed'])
            self.assertEqual(before, (root / 'data/memory.sqlite3').read_bytes())

    def test_package_scan_still_detects_runtime_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(root)
            report = verify(root, scan_artifacts=True)
            self.assertFalse(report['pass'])
            self.assertEqual(2, len(report['private_artifacts']))

    def test_source_mismatch_rejected_with_runtime_files_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_tree(root)
            (root / 'core.py').write_text('value = 2\n')
            with patch('tools.preflight.verify', side_effect=lambda: verify(root)):
                self.assertFalse(check_file(root / '.env')['passed'])

    def test_help_without_configuration(self):
        entry = Path(__file__).resolve().parents[1] / 'run_v4.py'
        result = subprocess.run([sys.executable, str(entry), '--help'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('--env-file', result.stdout)

    def test_packaged_cli_resolves_repository_resources(self):
        from mneme_asterion.cli import configure
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ):
            root = Path(tmp)
            env_file = root / 'fixture.env'
            env_file.write_text('\n'.join(k + '=' + v for k, v in self.values.items()))
            database = root / 'data' / 'memory.sqlite3'
            self.assertEqual(configure(env_file, database), database.resolve())
            repository = Path(__file__).resolve().parents[1]
            self.assertEqual(Path(os.environ['TIKTOKEN_CACHE_DIR']), repository / 'tokenizer-cache')
            self.assertTrue(database.parent.is_dir())


if __name__ == '__main__':
    unittest.main()
