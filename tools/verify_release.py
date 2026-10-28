"""Verify source fingerprints; optionally inspect a distribution directory."""
import argparse
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]

def verify(root=ROOT, *, scan_artifacts=False):
    root=Path(root).resolve()
    expected=json.loads((root/'provenance/CORE_SHA256.json').read_text(encoding='utf-8'))
    errors=[]
    for name,digest in expected.items():
        p=(root/name).resolve()
        if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:errors.append('Changed algorithm/source: '+name)
    private=[]
    for p in root.rglob('*') if scan_artifacts else ():
        if not p.is_file() or any(x in p.parts for x in ('.venv','__pycache__','.git')):continue
        name=p.name
        if (name.startswith('.env') and name!='.env.example') or p.suffix in {'.sqlite','.sqlite3','.db','.pem','.key'}:
            private.append(str(p.relative_to(root)))
        if p.suffix in {'.py','.md','.txt','.json'} or name=='.env.example':
            text=p.read_text(encoding='utf-8',errors='replace')
            if re.search(r'\bsk-[A-Za-z0-9_-]{20,}',text):errors.append('Credential pattern: '+str(p.relative_to(root)))
    return {'algorithm_files_checked':len(expected),'algorithm_match':not any(x.startswith('Changed') for x in errors),
            'package_scan':scan_artifacts,'private_artifacts':private,'errors':errors,'pass':not errors and not private}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',action='store_true',help='Also scan the distribution for runtime files and credentials')
    args=parser.parse_args()
    result=verify(scan_artifacts=args.package);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['pass'] else 1)
