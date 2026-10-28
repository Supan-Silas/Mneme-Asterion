"""Validate the V4 runtime profile and source fingerprints."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reproduction.serve import read_profile
from tools.verify_release import verify


def check_values(values):
    errors = []
    for key, expected in {'P2_SCOPED_STATE': '1', 'AMI_LLM_MODEL': 'gpt-4o-mini',
                          'AMI_EMBED_MODEL': 'text-embedding-v4',
                          'AMI_EMBED_BACKEND': 'openai'}.items():
        if values.get(key) != expected:
            errors.append(key + ' must be ' + expected)
    # The V4 service profile uses Bearer authentication.
    if values.get('AMI_AUTH_SCHEME', '').lower() != 'bearer':
        errors.append('AMI_AUTH_SCHEME must be bearer for this release')
    for key in ('AMI_AUTH_TOKEN', 'OPENAI_API_KEY', 'OPENAI_BASE_URL',
                'AMI_EMBED_API_KEY', 'AMI_EMBED_BASE_URL'):
        if not values.get(key, '').strip():
            errors.append('Missing required setting: ' + key)
    return errors


def check_file(path):
    errors = check_values(read_profile(Path(path).resolve()))
    source = verify()
    if not source['pass']:
        errors.append('Core source fingerprint check failed')
    return {'passed': not errors, 'method': 'ScopedStateV4',
            'errors': errors, 'source_check': source, 'api_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    args = parser.parse_args()
    result = check_file(args.env_file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
