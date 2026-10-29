"""Standalone AMI+E Add/Search service. One process/worker per database."""
import hashlib
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException
from pydantic import Field
from app import main as native, config, store, llm, runtime
from e_core.methods import raw_records, supplement, compose
from . import raw_store, model
from .context import pack

_locks = {}
_locks_guard = threading.Lock()
_count = None


@contextmanager
def user_lock(user):
    # Exact user keys with waiter reference counts: no hash-bucket collisions.
    with _locks_guard:
        entry = _locks.setdefault(user, [threading.RLock(), 0])
        entry[1] += 1
    try:
        with runtime.acquire(entry[0], 'user_lock'):
            yield
    finally:
        with _locks_guard:
            entry[1] -= 1
            if entry[1] == 0:
                del _locks[user]


class Message(native.Message):
    speaker: str | None = None
    source_id: str | None = None


class AddRequest(native.AddRequest):
    messages: list[Message] = Field(min_length=1)


@asynccontextmanager
async def lifespan(app):
    global _count
    if not __debug__:
        raise RuntimeError('Optimized Python disables source validators; run without -O')
    native.startup()
    # FULL durability on both connections: preserve successful Add across crash.
    with store._lock:
        store._conn.execute('PRAGMA synchronous=FULL')
    raw_store.init()
    if _count is None:
        import tiktoken
        enc = tiktoken.encoding_for_model(config.LLM_MODEL)
        _count = lambda text: len(enc.encode(text, disallowed_special=()))
    yield


app = FastAPI(title='Mneme-Asterion E', version='e-system-20261023', lifespan=lifespan)
app.add_middleware(native.AdmissionValve)
app.add_exception_handler(llm.UpstreamUnavailable, native.upstream_unavailable)
app.add_exception_handler(runtime.PermanentProviderError, native.provider_configuration_error)


@app.get('/health')
def health(authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)):
    return native.health(authorization, x_api_key)


@app.post('/add', response_model=native.AddResponse)
def add(request: AddRequest, authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)):
    native.check_auth(authorization, x_api_key)
    with runtime.request_scope(), user_lock(request.user_id):
        try:
            raw_store.stage(request)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        messages = []
        for m in request.messages:
            prefix = '[Recording date unknown; preserve source order; do not infer dates from ingestion time] ' if m.timestamp is None else ''
            content = f'{m.speaker}: {m.content}' if m.speaker else m.content
            messages.append({'role': m.role, 'content': prefix + content, 'timestamp': m.timestamp})
        adapted = native.AddRequest(request_id=request.request_id, user_id=request.user_id,
                                    session_id=request.session_id, messages=messages)
        return native.add(adapted, authorization, x_api_key)


@app.post('/search')
def search(request: native.SearchRequest, authorization: str | None = Header(default=None), x_api_key: str | None = Header(default=None)):
    native.check_auth(authorization, x_api_key)
    if request.top_k <= 0:
        return {'data': []}
    with runtime.request_scope(), user_lock(request.user_id):
        history = raw_store.history(request.user_id)
        # Fixed E baseline/context is top100, then respect the caller's output cap.
        baseline = native.search(request.model_copy(update={'top_k': 100}), authorization, x_api_key)
        base = [{'id': str(x['id']), 'text': x['content'], 'source_ids': [], 'timestamp': None, 'metadata': {}}
                for x in baseline['data']]
        if not history['sessions']:
            return {'data': baseline['data'][:min(100, request.top_k)]}
        records = raw_records(history, _count)
        try:
            supports, trace = supplement(request.query, pack(base, _count), records, model.call, _count)
        except llm.UpstreamUnavailable:
            raise
        except Exception as exc:
            # No provider response/prompt/key is exposed in the API error.
            raise HTTPException(502, 'E supplementation failed; baseline-only output was not substituted') from exc
        combined = compose(base, supports)[:min(100, request.top_k)]
        originals = {str(x['id']): x for x in baseline['data']}
        data = [originals[x['id']] if x['id'] in originals else
                {'id': x['id'], 'content': x['text'], 'score': 1.0, 'source_ids': x['source_ids']} for x in combined]
        return {'data': data, 'method': 'E', 'e_meta': {
            'supplements': len(supports), 'needed': trace['plan']['needed'],
            'source_recovery': bool(trace.get('decision', {}).get('schema_repair'))}}
