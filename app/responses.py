"""Единый формат JSON-ответов API: {"success": ..., "data": ..., "error": ...}."""

from typing import Any

from flask import Response, jsonify


def success(data: Any, status: int = 200) -> tuple[Response, int]:
    return jsonify({"success": True, "data": data, "error": None}), status
