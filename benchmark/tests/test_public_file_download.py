"""Pinned public bytes must be verified before publication as a local source."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.download_all_public_sources import download_files


class PublicFileDownloadTests(unittest.TestCase):
    def spec(self, body):
        return {'repo_id': 'synthetic', 'revision': 'test', 'scope': 'artificial file',
                'files': [{'path': 'sample.json', 'bytes': len(body),
                           'sha256': hashlib.sha256(body).hexdigest(), 'url': 'https://example.invalid/sample'}]}

    def test_verified_file_is_reusable_without_network(self):
        body = b'{"synthetic": true}\n'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('urllib.request.urlopen', return_value=io.BytesIO(body)) as request:
                download_files('source', self.spec(body), root)
                self.assertEqual(request.call_count, 1)
            with patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):
                download_files('source', self.spec(body), root)
            manifest = json.loads((root / 'source/download_manifest.json').read_text())
            self.assertEqual(manifest['status'], 'complete')

    def test_corrupt_download_never_replaces_valid_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').mkdir()
            target = root / 'source/sample.json'
            target.write_bytes(b'old source')
            with patch('urllib.request.urlopen', return_value=io.BytesIO(b'corrupt')):
                with self.assertRaises(ValueError):
                    download_files('source', self.spec(b'pinned source'), root)
            self.assertEqual(target.read_bytes(), b'old source')
            self.assertFalse((root / 'source/download_manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
