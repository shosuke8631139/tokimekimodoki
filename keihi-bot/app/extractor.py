"""OpenAI API(画像入力 + Structured Outputs)で領収書情報を抽出する。"""

import base64
import json

import httpx

from .models import Receipt

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """あなたは経理アシスタントです。添付の領収書画像から情報を抽出し、
指定のJSONスキーマのみで回答してください。
- 金額は税込合計(円・整数)。手書きや不鮮明で確信が持てない場合は
  confidence を下げ、notes に理由を書くこと
- 日付・金額などが読めない場合は null とし、推測で埋めないこと
- category は日本の一般的な勘定科目(会議費/旅費交通費/消耗品費/接待交際費 など)から選ぶこと
- 領収書やレシートではない画像だった場合は amount を null、confidence を 0 とし、
  notes に「領収書ではない」と書くこと"""

RECEIPT_JSON_SCHEMA = {
    "name": "receipt",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
            "amount": {"type": ["integer", "null"], "description": "税込合計(円)"},
            "vendor": {"type": ["string", "null"]},
            "category": {"type": ["string", "null"]},
            "tax_rate": {"type": ["integer", "null"], "description": "8 または 10"},
            "confidence": {"type": "number"},
            "notes": {"type": ["string", "null"]},
        },
        "required": [
            "date",
            "amount",
            "vendor",
            "category",
            "tax_rate",
            "confidence",
            "notes",
        ],
        "additionalProperties": False,
    },
}


def parse_receipt_json(raw: str) -> Receipt:
    """モデルの応答(JSON文字列)を Receipt に変換する。テスト容易性のため分離。"""
    data = json.loads(raw)
    # confidence が範囲外でも落ちないよう丸める
    conf = data.get("confidence", 0.0)
    try:
        data["confidence"] = min(1.0, max(0.0, float(conf)))
    except (TypeError, ValueError):
        data["confidence"] = 0.0
    return Receipt(**data)


class ReceiptExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4o", timeout: float = 60.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def extract(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Receipt:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "この領収書を読み取ってください。"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                        },
                    ],
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": RECEIPT_JSON_SCHEMA,
            },
            "temperature": 0,
        }
        resp = httpx.post(
            OPENAI_CHAT_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_receipt_json(content)
