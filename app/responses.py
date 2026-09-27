"""Единый формат JSON-ответов API: {"success": ..., "data": ..., "error": ...}."""

from collections.abc import Mapping
from typing import Any

from flask import Response, jsonify


def success(data: Any, status: int = 200) -> Response:
    return _envelope(is_success=True, data=data, message=None, status=status)


def error(message: str, status: int, headers: Mapping[str, str] | None = None) -> Response:
    response = _envelope(is_success=False, data=None, message=message, status=status)
    response.headers.update(headers or {})
    return response


def _envelope(*, is_success: bool, data: Any, message: str | None, status: int) -> Response:
    response = jsonify({"success": is_success, "data": data, "error": message})
    response.status_code = status
    return response
