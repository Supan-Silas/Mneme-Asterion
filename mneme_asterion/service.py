"""HTTP adapter for Mneme-Asterion memory retrieval."""
import json
import os
import logging
from fastapi import Header, HTTPException
from app import config, llm, runtime
from mneme_e import service as original, raw_store
from memory_benchmark.pipeline.context import GPTTokenizer
from e_core.methods import raw_records
from mneme_asterion.retrieval.quotes import generate_r1q
from mneme_asterion.state.policy import generate_state_policy
from mneme_asterion.availability import retrieve, protect

app = original.app
METHOD = 'ScopedStateV4' if os.environ.get('P2_SCOPED_STATE', '0') == '1' else 'P2'
app.title = 'Mneme-Asterion ' + METHOD
app.version = '4.1.0'
app.router.routes[:] = [r for r in app.router.routes if getattr(r, 'path', '') != '/search']

def call(prompt, stage, valid):
    header, payload = prompt.rsplit('\n', 1)
    def check(text):
        if text.startswith('```') and text.endswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        value = json.loads(text)  # new local value on every attempt
        valid(value)
        return value
    # Never recover an invalid decision by dropping edits or required protection.
    return runtime.chat(stage, [{'role':'system','content':header},
                        {'role':'user','content':payload}],
                        1000 if stage == 'P2P_relevance' else 8192, check,
                        seed=17, response_format={'type':'json_object'})


def encode_result(evidence, originals, top_k):
    # Always use transformed text: P2 can redact or prefix an existing ID.
    # Reusing the original object by ID would silently undo withdrawal filtering.
    by_id = {str(x['id']): x for x in originals}
    return [{'id': x['id'], 'content': x['text'],
             'score': by_id.get(x['id'], {}).get('score', 1.0),
             'source_ids': list(x.get('source_ids', []))}
            for x in evidence[:min(100, max(0, top_k))]]

@app.post('/search')
def search(request: original.native.SearchRequest,
           authorization: str | None = Header(default=None),
           x_api_key: str | None = Header(default=None)):
    original.native.check_auth(authorization, x_api_key)
    if request.top_k <= 0:
        return {'data': [], 'method': METHOD}
    with runtime.request_scope(), original.user_lock(request.user_id):
        history = raw_store.history(request.user_id)
        baseline = original.native.search(request.model_copy(update={'top_k': 100}), authorization, x_api_key)
        base = [{'id': str(x['id']), 'text': x['content'], 'source_ids': x.get('source_ids', []),
                 'timestamp': None, 'metadata': {}} for x in baseline['data']]
        if not history['sessions']:
            return {'data': baseline['data'][:min(100, request.top_k)], 'method': METHOD}
        tok = GPTTokenizer('gpt-4o-mini')
        raw = raw_records(history, tok.count)
        try:
            evidence, _ = retrieve(generate_r1q, request.query, base, raw, call, tok)
            evidence, protection = protect(generate_state_policy, request.query, evidence, raw, call, tok)
            if not protection.get('degraded') and os.environ.get('P2_SCOPED_STATE', '0') == '1':
                from mneme_asterion.state.adapter import apply as apply_scoped_state
                evidence, _ = apply_scoped_state(request.query, evidence, raw, config.DB_PATH, request.user_id, tok.count)
        except (llm.UpstreamUnavailable, runtime.PermanentProviderError):
            raise
        except Exception as exc:
            logging.getLogger('p2').error('P2 transform failed: %s', type(exc).__name__)
            raise HTTPException(502, {'reason':'internal transformation error','stage':'search.transform','retryable':False}) from exc
        return {'data': encode_result(evidence, baseline['data'], request.top_k), 'method': METHOD}
