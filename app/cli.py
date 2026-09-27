"""CLI-команды: `flask --app wsgi init-db`, `flask --app wsgi create-user <логин>`."""

import click
from flask import Flask
from flask.cli import with_appcontext

from app.auth.users import UserError, create_user
from app.extensions import db


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """Создать таблицы в базе данных."""
    db.create_all()
    click.echo("Таблицы созданы")


@click.command("create-user")
@click.argument("username")
@click.password_option(help="Пароль (запрашивается скрыто, с подтверждением)")
@with_appcontext
def create_user_command(username: str, password: str) -> None:
    """Создать пользователя с хэшированным паролем."""
    try:
        user = create_user(username, password)
    except UserError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Пользователь {user.username} создан (id={user.id})")


def register_cli(app: Flask) -> None:
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_user_command)
