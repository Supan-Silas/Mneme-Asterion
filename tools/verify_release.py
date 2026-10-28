"""Verify frozen algorithm bytes and detect private/generated artifacts."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]

def verify():
    expected=json.loads((ROOT/'provenance/ALGORITHM_SHA256.json').read_text(encoding='utf-8'))
    errors=[]
    for name,digest in expected.items():
        p=ROOT/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:errors.append('Changed algorithm/source: '+name)
    private=[]
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('.venv','__pycache__','.git')):continue
        name=p.name
        if (name.startswith('.env') and name!='.env.example') or p.suffix in {'.sqlite','.sqlite3','.db','.pem','.key'}:
            private.append(str(p.relative_to(ROOT)))
        if p.suffix in {'.py','.md','.txt','.json'} or name=='.env.example':
            text=p.read_text(encoding='utf-8',errors='replace')
            if re.search(r'\bsk-[A-Za-z0-9_-]{20,}',text):errors.append('Possible provider key: '+str(p.relative_to(ROOT)))
    return {'algorithm_files_checked':len(expected),'algorithm_match':not any(x.startswith('Changed') for x in errors),
            'private_artifacts':private,'errors':errors,'pass':not errors and not private,
            'note':'Pattern/file checks are not a guarantee against every possible secret format.'}

if __name__=='__main__':
    result=verify();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['pass'] else 1)
