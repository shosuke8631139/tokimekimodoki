import base64
import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Receipt

SECRET = "test-channel-secret"


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        line_channel_secret=SECRET,
        line_channel_access_token="dummy-token",
        openai_api_key="dummy-key",
        register_mode="csv",
        data_dir=tmp_path,
    )
    return TestClient(create_app(settings))


def sign(body: bytes) -> str:
    return base64.b64encode(
        hmac.new(SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()


def post_event(client: TestClient, payload: dict, signature: str | None = None):
    body = json.dumps(payload).encode()
    return client.post(
        "/callback",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Line-Signature": signature if signature is not None else sign(body),
        },
    )


def test_rejects_bad_signature(tmp_path):
    client = make_client(tmp_path)
    resp = post_event(client, {"events": []}, signature="wrong")
    assert resp.status_code == 403


def test_image_event_replies_with_confirmation(tmp_path):
    client = make_client(tmp_path)
    fake_receipt = Receipt(
        date="2026-07-21",
        amount=1980,
        vendor="テスト商店",
        category="消耗品費",
        tax_rate=10,
        confidence=0.9,
        notes=None,
    )
    payload = {
        "events": [
            {
                "type": "message",
                "replyToken": "rtoken",
                "message": {"type": "image", "id": "msg-100"},
            }
        ]
    }
    with (
        patch("app.line_client.LineClient.get_message_content", return_value=b"jpeg"),
        patch("app.extractor.ReceiptExtractor.extract", return_value=fake_receipt),
        patch("app.line_client.LineClient.reply_confirm") as mock_confirm,
    ):
        resp = post_event(client, payload)
        assert resp.status_code == 200
        # TestClient は BackgroundTasks をレスポンス前に同期実行する
        mock_confirm.assert_called_once()
        text = mock_confirm.call_args.args[1]
        assert "1,980円" in text

        # 同じメッセージIDの再送は二重処理されない
        mock_confirm.reset_mock()
        resp = post_event(client, payload)
        assert resp.status_code == 200
        mock_confirm.assert_not_called()
