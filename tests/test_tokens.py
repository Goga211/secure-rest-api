import base64
import json
import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.tokens import JWT_ALGORITHM, JWT_ISSUER, TokenError, decode_token, issue_token

SECRET = secrets.token_urlsafe(48)
OTHER_SECRET = secrets.token_urlsafe(48)


def _claims(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "1",
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return {**claims, **overrides}


def test_issued_token_decodes_to_user_id() -> None:
    issued = issue_token(42, SECRET, ttl_minutes=15)

    assert decode_token(issued.token, SECRET) == 42
    assert issued.expires_in == 15 * 60


def test_token_has_expected_claims() -> None:
    issued = issue_token(42, SECRET, ttl_minutes=15)

    payload = jwt.decode(issued.token, SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER)

    assert payload["sub"] == "42"
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_token_signed_with_other_secret_is_rejected() -> None:
    issued = issue_token(1, OTHER_SECRET, ttl_minutes=15)

    with pytest.raises(TokenError):
        decode_token(issued.token, SECRET)


def test_expired_token_is_rejected() -> None:
    issued = issue_token(1, SECRET, ttl_minutes=15, now=datetime.now(UTC) - timedelta(hours=1))

    with pytest.raises(TokenError):
        decode_token(issued.token, SECRET)


def test_tampered_payload_is_rejected() -> None:
    header, _, signature = issue_token(1, SECRET, ttl_minutes=15).token.split(".")
    forged_payload = {"sub": "2", "iss": JWT_ISSUER, "iat": 0, "exp": 9999999999}
    forged = base64.urlsafe_b64encode(json.dumps(forged_payload).encode()).rstrip(b"=").decode()

    with pytest.raises(TokenError):
        decode_token(f"{header}.{forged}.{signature}", SECRET)


def test_alg_none_token_is_rejected() -> None:
    unsigned = jwt.encode(_claims(), key="", algorithm="none")

    with pytest.raises(TokenError):
        decode_token(unsigned, SECRET)


def test_token_with_foreign_issuer_is_rejected() -> None:
    foreign = jwt.encode(_claims(iss="someone-else"), SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenError):
        decode_token(foreign, SECRET)


def test_token_without_expiration_is_rejected() -> None:
    claims = {key: value for key, value in _claims().items() if key != "exp"}
    endless = jwt.encode(claims, SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenError):
        decode_token(endless, SECRET)


def test_non_numeric_subject_is_rejected() -> None:
    odd = jwt.encode(_claims(sub="admin"), SECRET, algorithm=JWT_ALGORITHM)

    with pytest.raises(TokenError):
        decode_token(odd, SECRET)


def test_garbage_is_rejected() -> None:
    with pytest.raises(TokenError):
        decode_token("not-a-jwt", SECRET)
