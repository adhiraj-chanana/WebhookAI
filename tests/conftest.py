from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.queue import get_redis

TEST_STRIPE_SECRET = "whsec_test_stripe_secret"
TEST_GITHUB_SECRET = "test_github_secret"
TEST_SLACK_SECRET = "test_slack_secret"


@pytest.fixture(autouse=True)
def patch_secrets(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", TEST_STRIPE_SECRET)
    monkeypatch.setattr(settings, "github_webhook_secret", TEST_GITHUB_SECRET)
    monkeypatch.setattr(settings, "slack_signing_secret", TEST_SLACK_SECRET)


@pytest.fixture()
def redis_client():
    """Mock Upstash HTTP client — no real network calls in tests."""
    mock = AsyncMock()
    mock.lpush = AsyncMock(return_value=1)
    return mock


@pytest.fixture()
def client(redis_client):
    """TestClient with the Upstash dependency overridden."""
    app.dependency_overrides[get_redis] = lambda: redis_client
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
