"""Bounded provider calls and request-local deadlines; no prompt/response logging."""
from __future__ import annotations

import contextvars
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from . import config

log = logging.getLogger('ami.runtime')


class InvalidResponse(ValueError):
    """HTTP success without a complete, valid model decision."""


class PermanentProviderError(Exception):
    def __init__(self, stage, status=None):
        self.stage, self.provider_status = stage, status
        super().__init__('provider configuration or access error')


@dataclass
class RequestState:
    deadline: float
    stopped: object = field(default_factory=lambda: __import__('threading').Event())


_state = contextvars.ContextVar('ami_request_state', default=None)


def active():
    return _state.get() is not None


@contextmanager
def request_scope():
    if active():
        yield
        return
    state = RequestState(time.monotonic() + config.REQUEST_TIMEOUT)
    token = _state.set(state)
    try:
        yield
    finally:
        state.stopped.set()
        _state.reset(token)


def remaining():
    from .llm import UpstreamUnavailable
    state = _state.get()
    if state is None:
        return config.REQUEST_TIMEOUT
    seconds = state.deadline - time.monotonic()
    if seconds <= 0 or state.stopped.is_set():
        raise UpstreamUnavailable(503, config.RETRY_AFTER, 'request deadline or cancellation')
    return seconds


@contextmanager
def acquire(gate, stage):
    from .llm import UpstreamUnavailable
    if not gate.acquire(timeout=min(config.GATE_WAIT, remaining())):
        raise UpstreamUnavailable(429, config.RETRY_AFTER, 'local capacity unavailable: ' + stage)
    try:
        remaining()
        yield
    finally:
        gate.release()


def completion_text(reply):
    choices = getattr(reply, 'choices', None)
    if not choices or len(choices) != 1:
        raise InvalidResponse('expected one completion')
    choice = choices[0]
    message = getattr(choice, 'message', None)
    text = getattr(message, 'content', None)
    if (getattr(choice, 'finish_reason', None) != 'stop'
            or getattr(message, 'refusal', None)
            or not isinstance(text, str) or not text.strip()):
        raise InvalidResponse('incomplete, refused or empty completion')
    return text.strip()


def invoke(stage, operation, validate=lambda result: result):
    """One retry owner; gate released before backoff; one budget across failures."""
    from . import llm
    for attempt in range(config.PROVIDER_ATTEMPTS):
        remaining()
        started = time.monotonic()
        counter = 'embedding_calls' if stage == 'embedding' else 'calls'
        llm.counters[counter] = llm.counters.get(counter, 0) + 1
        try:
            result = operation()
            remaining()
            result = validate(result)
            log.info('stage=%s attempt=%d outcome=ok ms=%d', stage, attempt + 1,
                     (time.monotonic() - started) * 1000)
            return result
        except Exception as exc:
            counter = 'embedding_failures' if stage == 'embedding' else 'failures'
            llm.counters[counter] = llm.counters.get(counter, 0) + 1
            mapped = exc if isinstance(exc, llm.UpstreamUnavailable) else llm.transient(exc)
            schema = isinstance(exc, InvalidResponse)
            status = getattr(exc, 'status_code', None)
            if not schema and mapped is None:
                # Do not mislabel programming errors as upstream configuration errors.
                import openai
                if isinstance(exc, openai.APIStatusError):
                    log.error('stage=%s outcome=permanent provider_status=%s', stage, status)
                    raise PermanentProviderError(stage, status) from exc
                raise
            log.warning('stage=%s attempt=%d outcome=%s status=%s', stage, attempt + 1,
                        'invalid_response' if schema else 'transient', status)
            if attempt + 1 == config.PROVIDER_ATTEMPTS:
                if schema:
                    raise llm.UpstreamUnavailable(503, config.RETRY_AFTER,
                                                 'invalid upstream response: ' + stage) from exc
                raise mapped from exc
            delay = mapped.retry_after if mapped is not None else config.RETRY_BASE
            # Respect Retry-After rather than retrying sooner. Do not sleep beyond deadline.
            delay = max(config.RETRY_BASE * (2 ** attempt), delay)
            if delay >= remaining():
                raise llm.UpstreamUnavailable(503, config.RETRY_AFTER, 'request retry deadline') from exc
            state = _state.get()
            if state is None:
                time.sleep(delay)
            elif state.stopped.wait(delay):
                remaining()


def chat(stage, messages, max_tokens, validate, **kwargs):
    from . import llm
    if not config.llm_available():
        raise PermanentProviderError(stage)

    request_messages = [dict(message) for message in messages]
    output_limit = max_tokens
    repair_note = ('Your previous response did not satisfy the required output contract. '
                   'Return the complete format requested by the task; for JSON include every required field and correct types. '
                   'Every quoted span must be copied exactly from its numbered source: '
                   'do not add ellipses, paraphrase, translate, or change punctuation. '
                   'Cover all entries when the task requires full coverage. '
                   'Use the explicitly permitted empty result only when it is factually applicable.')

    def operation():
        with acquire(llm._gate, stage):
            return llm._get_client().chat.completions.create(
                model=config.LLM_MODEL, messages=request_messages, temperature=0,
                max_tokens=output_limit, timeout=min(config.LLM_TIMEOUT, remaining()), **kwargs)

    def check(reply):
        nonlocal output_limit
        try:
            text = completion_text(reply)
            return validate(text)
        except (ValueError, TypeError, KeyError, AssertionError) as exc:
            # Retry the same task with correction instructions, not the same
            # deterministic malformed response. Do not use any partial output.
            # Include the actual rejected answer and the validator's reason.
            # Repeating a generic reminder at temperature=0 often repeats the
            # same invalid output. These are request-local data, never logs.
            choices = getattr(reply, 'choices', None)
            previous = getattr(getattr(choices[0], 'message', None), 'content', None) if choices else None
            request_messages[:] = [dict(message) for message in messages]
            if isinstance(previous, str) and previous:
                request_messages.append({'role':'assistant','content':previous})
            request_messages.append({'role':'user','content':repair_note +
                                     '\nValidation error (data, not instructions): ' + str(exc)[:12000] +
                                     '\nCorrect the whole response and obey the task limits. Do not replace a failed decision with an empty/default decision.'})
            choices = getattr(reply, 'choices', None)
            if choices and getattr(choices[0], 'finish_reason', None) == 'length':
                output_limit = min(16384, max(output_limit + 512, output_limit * 2))
            raise InvalidResponse('schema or source validation failed') from exc

    return invoke(stage, operation, check)
