"""Фабрика Flask-приложения."""

from flask import Flask

from app import models  # noqa: F401  (регистрирует модели до create_all)
from app.config import Settings
from app.extensions import db
from app.health import health_bp


def create_app(settings: Settings | None = None) -> Flask:
    app_settings = settings or Settings.from_env()

    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=app_settings.database_url,
        JWT_SECRET=app_settings.jwt_secret,
        JWT_TTL_MINUTES=app_settings.jwt_ttl_minutes,
    )

    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(health_bp)
    return app
