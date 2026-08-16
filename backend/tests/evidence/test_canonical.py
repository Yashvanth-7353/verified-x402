import json
from datetime import datetime, timezone
from uuid import UUID

from app.evidence.canonical import canonicalize

def test_canonicalize_dict_ordering():
    dict1 = {"b": 2, "a": 1, "c": 3}
    dict2 = {"c": 3, "b": 2, "a": 1}
    assert canonicalize(dict1) == canonicalize(dict2)
    assert canonicalize(dict1) == '{"a":1,"b":2,"c":3}'

def test_canonicalize_whitespace():
    # Canonicalize should strip all unnecessary spaces
    assert canonicalize({"a": 1}) == '{"a":1}'

def test_canonicalize_datetime():
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    canon = canonicalize({"time": dt})
    assert canon == '{"time":"2026-01-01T12:00:00Z"}'

def test_canonicalize_uuid():
    u = UUID("12345678-1234-5678-1234-567812345678")
    assert canonicalize({"id": u}) == '{"id":"12345678-1234-5678-1234-567812345678"}'
