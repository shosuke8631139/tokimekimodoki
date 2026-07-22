"""LINE Messaging API まわり(署名検証・画像取得・返信)。"""

import base64
import hashlib
import hmac

import httpx

LINE_API_BASE = "https://api.line.me/v2/bot"
LINE_DATA_API_BASE = "https://api-data.line.me/v2/bot"


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    """X-Line-Signature の検証。不一致のリクエストは処理してはいけない。"""
    if not channel_secret or not signature:
        return False
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


class LineClient:
    def __init__(self, access_token: str, timeout: float = 15.0):
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._timeout = timeout

    def get_message_content(self, message_id: str) -> bytes:
        """ユーザーが送った画像バイナリを取得する。"""
        url = f"{LINE_DATA_API_BASE}/message/{message_id}/content"
        resp = httpx.get(url, headers=self._headers, timeout=self._timeout)
        resp.raise_for_status()
        return resp.content

    def reply(self, reply_token: str, messages: list[dict]) -> None:
        url = f"{LINE_API_BASE}/message/reply"
        resp = httpx.post(
            url,
            headers={**self._headers, "Content-Type": "application/json"},
            json={"replyToken": reply_token, "messages": messages},
            timeout=self._timeout,
        )
        resp.raise_for_status()

    def reply_text(self, reply_token: str, text: str) -> None:
        self.reply(reply_token, [{"type": "text", "text": text}])

    def reply_confirm(self, reply_token: str, text: str, token: str) -> None:
        """読み取り結果と「登録する/しない」のボタンを返す。"""
        self.reply(
            reply_token,
            [
                {
                    "type": "template",
                    "altText": text,
                    "template": {
                        "type": "confirm",
                        "text": text[:240],  # confirm template の文字数上限対策
                        "actions": [
                            {
                                "type": "postback",
                                "label": "登録する",
                                "data": f"action=confirm&token={token}",
                            },
                            {
                                "type": "postback",
                                "label": "登録しない",
                                "data": f"action=cancel&token={token}",
                            },
                        ],
                    },
                }
            ],
        )
