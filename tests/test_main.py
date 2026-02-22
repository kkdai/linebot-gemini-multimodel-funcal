# tests/test_main.py
import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture(autouse=False)
def patched_env():
    """Patch environment variables for testing."""
    with patch.dict("os.environ", {
        "ChannelSecret": "test-secret-12345678901234567890",
        "ChannelAccessToken": "test-token",
        "GOOGLE_API_KEY": "test-key",
        "BOT_HOST_URL": "https://test.example.com",
    }, clear=False):
        yield


@pytest.fixture
def app_client(patched_env):
    """Create FastAPI test client with mocked dependencies."""
    with patch("multi_tool_agent.ecommerce_agent.genai.Client"):
        import importlib
        import sys
        # Remove cached module to force reload with new env vars
        for key in list(sys.modules.keys()):
            if key == "main":
                del sys.modules[key]
        import main
        from fastapi.testclient import TestClient
        yield TestClient(main.app), main


def test_image_endpoint_404_for_unknown_id(app_client):
    client, _ = app_client
    response = client.get("/images/nonexistent-uuid")
    assert response.status_code == 404


def test_image_endpoint_returns_jpeg(app_client):
    client, main_module = app_client
    test_id = str(uuid.uuid4())
    # JPEG magic bytes + padding
    main_module.image_cache[test_id] = b'\xff\xd8\xff\xe0' + b'\x00' * 100
    response = client.get(f"/images/{test_id}")
    assert response.status_code == 200
    assert "image/jpeg" in response.headers["content-type"]


def test_image_endpoint_returns_correct_bytes(app_client):
    client, main_module = app_client
    test_id = str(uuid.uuid4())
    expected = b'\xff\xd8\xff\xe0test_image_data'
    main_module.image_cache[test_id] = expected
    response = client.get(f"/images/{test_id}")
    assert response.content == expected
