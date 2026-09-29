"""Настройки приложения из переменных окружения. Секреты в коде не хранятся."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_DATABASE_URL = "sqlite:///app.db"
DEFAULT_JWT_TTL_MINUTES = 15
MAX_JWT_TTL_MINUTES = 24 * 60
MIN_JWT_SECRET_LENGTH = 32
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


class ConfigError(ValueError):
    """Некорректная или неполная конфигурация."""


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str = field(repr=False)
    jwt_ttl_minutes: int = DEFAULT_JWT_TTL_MINUTES
    rate_limit_enabled: bool = True

    def __post_init__(self) -> None:
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise ConfigError(
                f"JWT_SECRET должен быть задан и содержать не менее "
                f"{MIN_JWT_SECRET_LENGTH} символов"
            )
        if not 1 <= self.jwt_ttl_minutes <= MAX_JWT_TTL_MINUTES:
            raise ConfigError(f"JWT_TTL_MINUTES должен быть от 1 до {MAX_JWT_TTL_MINUTES}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        return cls(
            database_url=source.get("DATABASE_URL", DEFAULT_DATABASE_URL),
            jwt_secret=source.get("JWT_SECRET", ""),
            jwt_ttl_minutes=_parse_int(
                source.get("JWT_TTL_MINUTES", str(DEFAULT_JWT_TTL_MINUTES)), "JWT_TTL_MINUTES"
            ),
            rate_limit_enabled=_parse_bool(
                source.get("RATE_LIMIT_ENABLED", "true"), "RATE_LIMIT_ENABLED"
            ),
        )


def _parse_int(raw: str, name: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} должен быть целым числом") from exc


def _parse_bool(raw: str, name: str) -> bool:
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    raise ConfigError(f"{name} должен быть true или false")
