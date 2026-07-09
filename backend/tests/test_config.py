from app.config import get_settings


def test_settings_load_from_env():
    settings = get_settings()

    assert settings.ANTHROPIC_API_KEY
    assert settings.DATABASE_URL
    assert settings.REDIS_URL
    assert settings.STORAGE_PATH
    assert settings.SECRET_KEY
