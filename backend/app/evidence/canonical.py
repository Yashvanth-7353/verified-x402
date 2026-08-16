import json
from datetime import datetime
from uuid import UUID
from enum import Enum
from pydantic import BaseModel

class CanonicalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if isinstance(obj, datetime):
            # Ensure ISO 8601 string, standardized to UTC format ending in 'Z'
            return obj.isoformat().replace("+00:00", "Z")
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)

def canonicalize(data) -> str:
    """
    Produces a deterministic JSON string representation of the data.
    Ensures key ordering and removes unnecessary whitespace.
    """
    if isinstance(data, BaseModel):
        # Let Pydantic convert it to dict with json serialization first
        data = data.model_dump(mode="json")
        
    return json.dumps(
        data,
        sort_keys=True,
        separators=(',', ':'),
        cls=CanonicalEncoder
    )
