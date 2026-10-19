"""Verify the published LF-normalized source manifest and deployed AMI identity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main():
    manifest = json.loads((ROOT / 'PUBLICATION_MANIFEST.json').read_text(encoding='utf-8'))
    failures = []
    for relative, expected in manifest['files_sha256'].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or digest(path) != expected:
            failures.append(relative)
    deployed = json.loads((ROOT / 'deploy/deployed-source.json').read_text(encoding='utf-8'))
    for relative, expected in deployed['python_sources'].items():
        if digest(ROOT / relative) != expected:
            failures.append('deployed AMI source: ' + relative)
    if (ROOT / 'VERSION').read_text().strip() != 'v0':
        failures.append('workbench VERSION')
    if (ROOT / 'benchmark/VERSION').read_text().strip() != 's_benchmark_v1':
        failures.append('benchmark VERSION')
    print(json.dumps({'release': 'v0', 'files_checked': len(manifest['files_sha256']),
                      'deployed_ami_files_checked': len(deployed['python_sources']),
                      'passed': not failures, 'failures': failures}, indent=2))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
