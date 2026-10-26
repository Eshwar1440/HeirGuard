import pytest

from hg import llm
from hg.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Keep tests off the real ai_log/ and away from any real API key."""
    monkeypatch.setenv("AI_LOG_DIR", str(tmp_path / "ai_log"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    real_get_client = llm.get_client
    get_settings.cache_clear()
    real_get_client.cache_clear()
    yield
    get_settings.cache_clear()
    real_get_client.cache_clear()
