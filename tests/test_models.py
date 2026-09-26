from collections.abc import Iterator

import pytest
from flask import Flask
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session

from app.extensions import db
from app.models import Post, User


@pytest.fixture
def session(app: Flask) -> Iterator[scoped_session]:
    with app.app_context():
        yield db.session
        db.session.remove()


def _make_user(username: str = "alice") -> User:
    return User(username=username, password_hash="not-a-real-hash")


def test_user_and_post_are_linked(session: scoped_session) -> None:
    user = _make_user()
    post = Post(title="Hello", body="First post", author=user)
    session.add_all([user, post])
    session.commit()

    stored = session.execute(db.select(User).filter_by(username="alice")).scalar_one()

    assert [p.title for p in stored.posts] == ["Hello"]
    assert stored.posts[0].author is stored
    assert stored.created_at is not None
    assert post.created_at is not None


def test_username_must_be_unique(session: scoped_session) -> None:
    session.add(_make_user("bob"))
    session.commit()

    session.add(_make_user("bob"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_post_requires_author(session: scoped_session) -> None:
    session.add(Post(title="Orphan", body="No author"))

    with pytest.raises(IntegrityError):
        session.commit()
