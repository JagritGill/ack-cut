"""Read a bounded, trusted stable local JSON file; never change it."""

import json
import os
from pathlib import Path
import stat

from .core import TraceError

MAX_BYTES = 2 * 1024 * 1024


def _pairs(entries: list) -> dict:
    result = {}
    for key, value in entries:
        if key in result:
            raise TraceError("duplicate JSON object member")
        result[key] = value
    return result


def _integer(token: str) -> int:
    if len(token) > 20:
        raise TraceError("integer token exceeds supported offset length")
    return int(token)


def _reject_number(_: str) -> None:
    raise TraceError("trace numbers must be JSON integers, not decimals or nonfinite constants")


def load_trace(path: str | Path) -> dict:
    try:
        source = Path(path)
        if not stat.S_ISREG(source.lstat().st_mode):
            raise TraceError("input must be a regular file, not a symlink or device")
        with source.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise TraceError("input must be a regular file")
            data = stream.read(MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        if isinstance(exc, TraceError):
            raise
        raise TraceError("cannot read local trace file") from None
    if len(data) > MAX_BYTES:
        raise TraceError(f"trace exceeds {MAX_BYTES} bytes")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_int=_integer,
                           parse_float=_reject_number, parse_constant=_reject_number)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise TraceError("invalid UTF-8 JSON or excessive nesting") from None
    if type(value) is not dict:
        raise TraceError("trace must be an object")
    return value
