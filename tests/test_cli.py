from flask import Flask
from sqlalchemy import inspect

from app import create_app
from app.auth.users import find_user
from app.config import Settings
from app.extensions import db

GOOD_PASSWORD = "long-enough-password"


def _password_input(password: str) -> str:
    # click.password_option спрашивает пароль и подтверждение
    return f"{password}\n{password}\n"


def test_init_db_creates_tables(settings: Settings) -> None:
    fresh_app = create_app(settings)

    result = fresh_app.test_cli_runner().invoke(args=["init-db"])

    assert result.exit_code == 0
    with fresh_app.app_context():
        assert {"users", "posts"} <= set(inspect(db.engine).get_table_names())


def test_create_user_command_creates_user(app: Flask) -> None:
    result = app.test_cli_runner().invoke(
        args=["create-user", "Alice"], input=_password_input(GOOD_PASSWORD)
    )

    assert result.exit_code == 0, result.output
    assert "alice" in result.output
    with app.app_context():
        assert find_user("alice") is not None


def test_create_user_command_reports_validation_error(app: Flask) -> None:
    result = app.test_cli_runner().invoke(
        args=["create-user", "alice"], input=_password_input("short")
    )

    assert result.exit_code != 0
    assert "Пароль" in result.output
    with app.app_context():
        assert find_user("alice") is None
