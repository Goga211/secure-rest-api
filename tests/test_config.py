import secrets

import pytest

from app import create_app
from app.config import DEFAULT_DATABASE_URL, DEFAULT_JWT_TTL_MINUTES, ConfigError, Settings

VALID_SECRET = secrets.token_urlsafe(48)


def test_from_env_reads_values() -> None:
    env = {
        "DATABASE_URL": "sqlite:///custom.db",
        "JWT_SECRET": VALID_SECRET,
        "JWT_TTL_MINUTES": "30",
    }

    settings = Settings.from_env(env)

    assert settings.database_url == "sqlite:///custom.db"
    assert settings.jwt_secret == VALID_SECRET
    assert settings.jwt_ttl_minutes == 30


def test_from_env_applies_defaults() -> None:
    settings = Settings.from_env({"JWT_SECRET": VALID_SECRET})

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.jwt_ttl_minutes == DEFAULT_JWT_TTL_MINUTES


def test_missing_secret_raises() -> None:
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        Settings.from_env({})


def test_short_secret_raises() -> None:
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        Settings.from_env({"JWT_SECRET": "short"})


def test_non_integer_ttl_raises() -> None:
    with pytest.raises(ConfigError, match="JWT_TTL_MINUTES"):
        Settings.from_env({"JWT_SECRET": VALID_SECRET, "JWT_TTL_MINUTES": "abc"})


@pytest.mark.parametrize("ttl", ["0", "-5", "1441"])
def test_out_of_range_ttl_raises(ttl: str) -> None:
    with pytest.raises(ConfigError, match="JWT_TTL_MINUTES"):
        Settings.from_env({"JWT_SECRET": VALID_SECRET, "JWT_TTL_MINUTES": ttl})


def test_repr_does_not_leak_secret() -> None:
    settings = Settings.from_env({"JWT_SECRET": VALID_SECRET})

    assert VALID_SECRET not in repr(settings)


def test_create_app_applies_settings() -> None:
    settings = Settings.from_env({"JWT_SECRET": VALID_SECRET, "JWT_TTL_MINUTES": "5"})

    app = create_app(settings)

    assert app.config["JWT_SECRET"] == VALID_SECRET
    assert app.config["JWT_TTL_MINUTES"] == 5
