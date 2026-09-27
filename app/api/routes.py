"""Эндпоинты с данными. Доступны только с валидным JWT."""

from flask import Blueprint, Response, request
from pydantic import ValidationError
from sqlalchemy.orm import selectinload

from app.api.schemas import CreatePostRequest
from app.api.serializers import post_to_dict
from app.auth.decorators import current_user, jwt_required
from app.extensions import db
from app.models import Post
from app.responses import error, success

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


@api_bp.post("/posts")
@jwt_required
def create_post() -> Response:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("Ожидается JSON-объект с полями title и body", 400)
    try:
        data = CreatePostRequest.model_validate(payload)
    except ValidationError:
        return error(
            "Поля title и body обязательны, должны быть непустыми строками допустимой длины",
            400,
        )

    # Автор берётся из токена, а не из тела запроса
    post = Post(title=data.title, body=data.body, author=current_user())
    db.session.add(post)
    db.session.commit()
    return success(post_to_dict(post), status=201)
