"""One synthetic Add/Search check. This makes paid calls on a real service."""
import argparse
import getpass
import json
import uuid
import httpx

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://127.0.0.1:8014')
    p.add_argument('--method', default='ScopedStateV4', choices=['ScopedStateV4', 'P2'])
    a = p.parse_args()
    token = getpass.getpass('Memory service token (not provider API key): ')
    scope = 'smoke-' + uuid.uuid4().hex
    with httpx.Client(base_url=a.url, headers={'Authorization': 'Bearer '+token},
                      timeout=600, trust_env=False) as c:
        c.get('/health').raise_for_status()
        payload = {'request_id': scope+':0', 'user_id': scope, 'session_id': 's1',
                   'messages': [{'role':'user', 'speaker':'Alice',
                                 'content':'My favorite instrument is the cello.'}]}
        r = c.post('/add', json=payload); r.raise_for_status()
        assert r.json().get('success') is True
        for k in ('request_id','user_id','session_id'): assert r.json()[k] == payload[k]
        r = c.post('/search', json={'user_id':scope, 'query':'What is Alice\'s favorite instrument?', 'top_k':100})
        r.raise_for_status()
        if r.json().get('method') != a.method:
            raise ValueError('Search method identity does not match --method')
        data=r.json()['data']
        assert isinstance(data,list) and 0 < len(data) <= 100
        assert all(isinstance(x.get('id'),str) and x['id'] and isinstance(x.get('content'),str) and x['content'].strip() for x in data)
        print(json.dumps({'status':'contract_passed','method':r.json().get('method'),
                          'evidence_count':len(data), 'scope':scope,
                          'quality_score':None},ensure_ascii=False))

if __name__ == '__main__': main()
