"""Real local process telemetry and cross-process locks; no models or datasets."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from memory_benchmark.runtime.locking import exclusive_lock
from memory_benchmark.runtime.resources import cpu_affinity, limits, process_usage
from memory_benchmark.runtime.worker import environment


class PlatformRuntimeTests(unittest.TestCase):
    def test_current_process_usage_and_environment(self):
        usage = process_usage()
        self.assertGreater(usage['peak_rss_bytes'], 0)
        self.assertGreaterEqual(usage['user_cpu_seconds'], 0)
        self.assertGreaterEqual(usage['system_cpu_seconds'], 0)
        info = environment()
        self.assertGreater(info['container_limits']['eligible_logical_cpus'], 0)
        affinity = cpu_affinity()
        if affinity is not None:
            self.assertTrue(affinity)
            self.assertEqual(affinity, sorted(set(affinity)))

    def test_cpu_count_fallback_without_affinity_api(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch('memory_benchmark.runtime.resources.cpu_affinity', return_value=None), \
                patch('memory_benchmark.runtime.resources.os.cpu_count', return_value=None):
            self.assertEqual(limits(Path(temp))['effective_cpu_cores'], 1)
            self.assertEqual(limits(Path(temp), affinity_count=3)['eligible_logical_cpus'], 3)

    def test_unix_usage_retains_platform_units(self):
        fake = SimpleNamespace(RUSAGE_SELF=0, getrusage=lambda _: SimpleNamespace(ru_utime=1.25, ru_stime=.5, ru_maxrss=123))
        with patch.dict(sys.modules, resource=fake):
            for platform, expected in [('linux', 123 * 1024), ('darwin', 123)]:
                with self.subTest(platform=platform), patch('memory_benchmark.runtime.resources.sys.platform', platform):
                    result = process_usage()
                    self.assertEqual(result['peak_rss_bytes'], expected)
                    self.assertEqual(result['user_cpu_seconds'], 1.25)

    def test_lock_excludes_other_process_and_releases_after_exception(self):
        code = '''import sys
from memory_benchmark.runtime.locking import exclusive_lock
try:
    with exclusive_lock(sys.argv[1]):
        pass
except OSError:
    sys.exit(2)
'''
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'queue.lock'
            def child():
                return subprocess.run([sys.executable, '-c', code, str(path)],
                    capture_output=True, text=True, timeout=10, env=os.environ.copy())
            with self.assertRaisesRegex(RuntimeError, 'fixture'):
                with exclusive_lock(path):
                    result = child()
                    self.assertEqual(result.returncode, 2, result.stderr)
                    raise RuntimeError('fixture')
            result = child()
            self.assertEqual(result.returncode, 0, result.stderr)
            # A stale lock file alone must not prevent restart.
            with exclusive_lock(path):
                self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()
