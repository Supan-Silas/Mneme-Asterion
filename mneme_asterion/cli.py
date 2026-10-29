"""Configure and run the Mneme-Asterion memory service."""
import argparse
import os
from pathlib import Path
from reproduction.serve import clear_model_environment, read_profile

ROOT = Path(__file__).resolve().parents[1]

def configure(env_file, db=None):
    values = read_profile(Path(env_file).resolve())
    for key in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'AMI_EMBED_API_KEY',
                'AMI_EMBED_BASE_URL', 'AMI_AUTH_TOKEN'):
        if not values.get(key, '').strip():
            raise ValueError('Missing required setting: ' + key)
    if values.get('AMI_LLM_MODEL') != 'gpt-4o-mini' or values.get('AMI_EMBED_MODEL') != 'text-embedding-v4':
        raise ValueError('This release requires gpt-4o-mini and text-embedding-v4')
    if values.get('AMI_EMBED_BACKEND') != 'openai':
        raise ValueError('This lightweight release requires the OpenAI-compatible embedding backend')
    clear_model_environment()
    os.environ.update(values)
    scoped = values.get('P2_SCOPED_STATE', '1')
    if scoped not in {'0', '1'}:
        raise ValueError('P2_SCOPED_STATE must be 0 or 1')
    os.environ['P2_SCOPED_STATE'] = scoped
    os.environ['TIKTOKEN_CACHE_DIR'] = str(ROOT / 'tokenizer-cache')
    database = Path(db or values.get('AMI_DB_PATH', './data/scoped-state-v4.sqlite3')).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    os.environ['AMI_DB_PATH'] = str(database)
    return database

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file', required=True)
    p.add_argument('--db')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8013)
    p.add_argument('--check', action='store_true', help='Validate configuration without API calls')
    a = p.parse_args()
    try:
        configure(a.env_file, a.db)
    except ValueError as e:
        p.error(str(e))
    if a.check:
        print('Configuration valid; values withheld; no API calls.')
        return
    import uvicorn
    from mneme_asterion.service import app
    uvicorn.run(app, host=a.host, port=a.port, workers=1, access_log=False)

if __name__ == '__main__':
    main()
