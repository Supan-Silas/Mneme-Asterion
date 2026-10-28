"""Verify every shipped file against SHA256SUMS.json, without network access."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def verify():
    expected = json.loads((ROOT / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    errors = []
    for name, digest in expected.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            errors.append('Missing or invalid path: ' + name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append('Changed: ' + name)
    return {'passed': not errors, 'files_checked': len(expected), 'errors': errors,
            'scope': 'shipped files; newly generated data is not covered'}


if __name__ == '__main__':
    result = verify()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
