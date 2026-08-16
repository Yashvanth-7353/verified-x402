from app.evidence.hasher import hash_data

def test_hasher_determinism():
    dict1 = {"b": 2, "a": 1}
    dict2 = {"a": 1, "b": 2}
    
    hash1 = hash_data(dict1)
    hash2 = hash_data(dict2)
    
    assert hash1 == hash2

def test_hasher_distinct():
    hash1 = hash_data({"a": 1})
    hash2 = hash_data({"a": 2})
    assert hash1 != hash2
