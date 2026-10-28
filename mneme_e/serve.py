"""Explicit configuration before importing either memory system."""
import argparse
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env-file', type=Path, required=True)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8023)
    args = p.parse_args()
    from reproduction.serve import read_profile, clear_model_environment
    profile = read_profile(args.env_file.resolve())
    required = ['AMI_AUTH_TOKEN', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'AMI_EMBED_API_KEY', 'AMI_EMBED_BASE_URL']
    if any(not profile.get(k, '').strip() for k in required):
        p.error('Fill all required credentials/endpoints in your private env file. Values are not printed.')
    if profile.get('AMI_AUTH_SCHEME') not in ['bearer', 'token', 'x-api-key']:
        p.error('Choose bearer, token or x-api-key authentication')
    if profile.get('AMI_LLM_MODEL') != 'gpt-4o-mini' or profile.get('AMI_EMBED_MODEL') != 'text-embedding-v4':
        p.error('This frozen profile uses gpt-4o-mini and text-embedding-v4')
    clear_model_environment()
    os.environ.update(profile)
    db = Path(profile.get('AMI_DB_PATH', './data/memory-e.sqlite3')).resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    os.environ['AMI_DB_PATH'] = str(db)
    import uvicorn
    from .service import app
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == '__main__': main()
