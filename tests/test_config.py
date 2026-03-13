

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "111,222")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4")
    monkeypatch.setenv("CLICKUP_API_TOKEN", "ck-token")
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "list-123")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

    from src.config.settings import Settings

    settings = Settings()

    assert settings.telegram_bot_token == "test-token"
    assert settings.telegram_allowed_user_ids == [111, 222]
    assert settings.openrouter_api_key == "or-key"
    assert settings.clickup_api_token == "ck-token"
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost/db"


def test_allowed_user_ids_parsed_as_list(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://x.com/w")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "100,200,300")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_MODEL_ID", "m")
    monkeypatch.setenv("CLICKUP_API_TOKEN", "c")
    monkeypatch.setenv("CLICKUP_DEFAULT_LIST_ID", "l")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

    from src.config.settings import Settings

    settings = Settings()
    assert settings.telegram_allowed_user_ids == [100, 200, 300]
