"""Проверка, что сервис жив."""

from flask import Blueprint, Response

from app.responses import success

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health() -> Response:
    return success({"status": "ok"})
