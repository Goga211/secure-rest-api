"""Эндпоинты с данными. Доступны только с валидным JWT."""

from flask import Blueprint, Response
from sqlalchemy.orm import selectinload

from app.api.serializers import post_to_dict
from app.auth.decorators import jwt_required
from app.extensions import db
from app.models import Post
from app.responses import success

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_POSTS = 100


@api_bp.get("/data")
@jwt_required
def list_posts() -> Response:
    statement = (
        db.select(Post)
        .options(selectinload(Post.author))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(MAX_POSTS)
    )
    posts = db.session.execute(statement).scalars()
    return success([post_to_dict(post) for post in posts])
