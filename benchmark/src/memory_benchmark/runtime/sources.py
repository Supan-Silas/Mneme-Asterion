"""Portable source-manifest verification, including Windows relative paths."""
from pathlib import Path, PurePosixPath, PureWindowsPath

from .artifacts import read_json


def manifest_key(value):
    value = str(value).replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
        raise ValueError("Source manifest paths must be relative and contained")
    return path.as_posix()


def verify_source_manifest(config, hashes):
    if not config.get("source_manifest"):
        return
    release = read_json(config["source_manifest"])
    expected = {}
    for entry in release["files"]:
        key = manifest_key(entry["path"])
        if key in expected:
            raise ValueError("Duplicate source manifest path")
        expected[key] = entry["sha256"]
    snapshot = Path(config["source_snapshot"]).resolve()
    for path, digest in hashes.items():
        relative = Path(path).resolve().relative_to(snapshot).as_posix()
        if digest != expected.get(relative):
            raise ValueError(f"Pinned public source file changed: {relative}")
