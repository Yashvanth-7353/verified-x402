import hashlib
from app.evidence.canonical import canonicalize

def hash_data(data) -> str:
    """
    Computes the SHA-256 hex digest of the canonicalized data.
    """
    canonical_str = canonicalize(data)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
