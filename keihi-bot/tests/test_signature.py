import base64
import hashlib
import hmac

from app.line_client import verify_signature

SECRET = "test-channel-secret"


def sign(body: bytes) -> str:
    return base64.b64encode(
        hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()


def test_valid_signature():
    body = b'{"events":[]}'
    assert verify_signature(SECRET, body, sign(body))


def test_invalid_signature():
    assert not verify_signature(SECRET, b'{"events":[]}', "deadbeef")


def test_empty_secret_or_signature():
    body = b"{}"
    assert not verify_signature("", body, sign(body))
    assert not verify_signature(SECRET, body, "")
