import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.repair.semantic import MockSemanticProvider


@pytest.fixture(autouse=True)
def _use_mock_semantic_provider():
    """Force MockSemanticProvider in ALL unit tests.
    
    This ensures tests never call the real Groq API and remain deterministic.
    Override this fixture in specific integration tests that need the real provider.
    """
    with patch("app.repair.semantic.get_default_provider", return_value=MockSemanticProvider()):
        yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
