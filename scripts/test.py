"""Run offline tests in isolated processes."""
from pathlib import Path
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
modules = ['tests.' + path.stem for path in sorted((ROOT / 'tests').glob('test_*.py'))]
env = {**os.environ, 'TIKTOKEN_CACHE_DIR': str(ROOT / 'tokenizer-cache'), 'PYTHONUTF8': '1'}
results = []
for module in modules:
    try:
        proc = subprocess.run([sys.executable, '-m', 'unittest', module], cwd=ROOT,
                              env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
        output = proc.stdout + proc.stderr
        matches = re.findall(r'Ran (\d+) tests?', output)
        result = {'module': module, 'passed': proc.returncode == 0,
                  'tests': int(matches[-1]) if matches else 0, 'output': output}
    except subprocess.TimeoutExpired:
        result = {'module': module, 'passed': False, 'tests': 0, 'output': 'Test process exceeded 120 seconds'}
    results.append(result)
summary = {'passed': all(r['passed'] for r in results),
           'tests': sum(r['tests'] for r in results), 'results': results}
print(json.dumps(summary, ensure_ascii=False, indent=2))
raise SystemExit(0 if summary['passed'] else 1)
