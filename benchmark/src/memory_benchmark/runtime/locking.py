"""Nonblocking coordinator lock, automatically released on close/process exit."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def exclusive_lock(path):
    with Path(path).open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            # Byte-range locking also works beyond EOF; do not modify a locked file.
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
