import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from .errors import require


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def uid():
    return uuid4().hex


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', value),
            'INVALID_INPUT', 'Invalid identifier')
    return value


def text(value, limit=65536):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit,
            'INVALID_INPUT', 'A bounded non-empty text value is required')
    return value
