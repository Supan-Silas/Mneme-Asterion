"""Download all six pinned public sources. Never contacts models or AML private APIs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return path.stat().st_size, digest.hexdigest()


def download_files(name, spec, root):
    folder = (root / name).resolve()
    if not folder.is_relative_to(root.resolve()):
        raise ValueError('Source folder escapes the download root')
    folder.mkdir(parents=True, exist_ok=True)
    verified = []
    for entry in spec['files']:
        target = (folder / entry['path']).resolve()
        if not target.is_relative_to(folder):
            raise ValueError('Source file escapes the source folder')
        expected = entry['bytes'], entry['sha256']
        if not target.is_file() or fingerprint(target) != expected:
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + '.download.partial')
            request = urllib.request.Request(entry['url'], headers={'User-Agent': 'Mneme-Asterion-public-data/1'})
            try:
                with urllib.request.urlopen(request, timeout=120) as response, partial.open('wb') as stream:
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
                if fingerprint(partial) != expected:
                    raise ValueError('Downloaded source bytes do not match the pinned SHA-256: ' + name)
                partial.replace(target)
            finally:
                if partial.exists():
                    partial.unlink()
        verified.append({key: entry[key] for key in ('path', 'bytes', 'sha256', 'url')})
    result = {'status': 'complete', 'repo_id': spec['repo_id'], 'revision': spec['revision'],
              'full_repository': False, 'scope': spec['scope'], 'files': verified}
    temporary_manifest = folder / 'download_manifest.json.tmp'
    temporary_manifest.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    temporary_manifest.replace(folder / 'download_manifest.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT / 'datasets/raw')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    root = args.root.resolve()
    lock = json.loads((ROOT / 'configs/datasets/file_sources.json').read_text(encoding='utf-8'))
    for name, spec in lock['datasets'].items():
        result = download_files(name, spec, root)
        print(name + ': verified ' + str(len(result['files'])) + ' pinned public files', flush=True)
    # Reuse the existing complete-repository/LFS downloader for the other four.
    return subprocess.run([sys.executable, str(ROOT / 'scripts/download_public_datasets.py'),
                           '--root', str(root), '--workers', str(args.workers)], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
