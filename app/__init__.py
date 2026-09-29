"""Фабрика Flask-приложения."""

from flask import Flask

from app import models  # noqa: F401  (регистрирует модели до create_all)
from app.api.routes import api_bp
from app.auth.routes import auth_bp
from app.cli import register_cli
from app.config import Settings
from app.errors import register_error_handlers
from app.extensions import db, limiter
from app.health import health_bp
from app.security import register_security_headers

# Предел размера тела запроса: всё, что больше, отклоняется с 413
MAX_CONTENT_LENGTH = 16 * 1024


def create_app(settings: Settings | None = None) -> Flask:
    app_settings = settings or Settings.from_env()

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=app_settings.database_url,
        JWT_SECRET=app_settings.jwt_secret,
        JWT_TTL_MINUTES=app_settings.jwt_ttl_minutes,
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
        RATELIMIT_ENABLED=app_settings.rate_limit_enabled,
    )

    db.init_app(app)
    limiter.init_app(app)
    register_cli(app)
    register_security_headers(app)
    register_error_handlers(app)
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    return app
