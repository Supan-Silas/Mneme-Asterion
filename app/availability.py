"""RC15: bounded optional enrichment; storage and identity errors never degrade."""
import functools
import logging
import time
from contextlib import contextmanager
from . import runtime

log = logging.getLogger('ami.availability')

def note(stage, exc):
    log.warning('stage=%s outcome=degraded reason=%s', stage,
                getattr(exc, 'reason', type(exc).__name__))

@contextmanager
def enrichment_budget(seconds=60):
    parent = runtime._state.get()
    deadline = time.monotonic() + seconds
    state = runtime.RequestState(min(deadline, parent.deadline) if parent else deadline)
    if parent is not None:
        state.stopped = parent.stopped
    token = runtime._state.set(state)
    try:
        yield
    finally:
        runtime._state.reset(token)

def optional(stage, fallback):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            from .llm import UpstreamUnavailable
            try:
                with enrichment_budget():
                    return fn(*args, **kwargs)
            except UpstreamUnavailable as exc:
                note(stage, exc)
                return fallback()
        return wrapped
    return decorate
