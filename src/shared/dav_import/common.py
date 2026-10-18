from shared.paths import resolve_path
import hashlib
import json
from datetime import datetime, timezone


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(dumps(value).encode('utf-8')).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(resolve_path(path), 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()
