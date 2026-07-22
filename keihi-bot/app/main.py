"""LINE Webhook 受信サーバー本体。

フロー:
1. 画像メッセージ受信 → 署名検証 → 冪等性チェック → 画像取得
2. OpenAI で領収書情報を抽出 → 承認待ちとして保存 → confirm テンプレートで返信
3. 「登録する」postback → マネーフォワード(CSV or API)へ登録 → 結果を返信
"""

import logging
from urllib.parse import parse_qs

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from .config import Settings, load_settings
from .extractor import ReceiptExtractor
from .line_client import LineClient, verify_signature
from .moneyforward import build_registrar
from .store import Store

logger = logging.getLogger("keihi-bot")
logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="keihi-bot")

    store = Store(settings.data_dir)
    line = LineClient(settings.line_channel_access_token)
    extractor = ReceiptExtractor(settings.openai_api_key, settings.openai_model)
    registrar = build_registrar(settings)

    def handle_image(message_id: str, reply_token: str) -> None:
        if not store.mark_processed(message_id):
            logger.info("skip duplicate message: %s", message_id)
            return
        try:
            image = line.get_message_content(message_id)
            receipt = extractor.extract(image)
        except Exception:
            logger.exception("extraction failed for %s", message_id)
            line.reply_text(reply_token, "読み取りに失敗しました。もう一度送ってみてください。")
            return

        if not receipt.is_receipt():
            line.reply_text(
                reply_token,
                "領収書として読み取れませんでした。"
                + (f"\n({receipt.notes})" if receipt.notes else ""),
            )
            return

        token = store.save_pending(receipt)
        lines = ["領収書を読み取りました。", *receipt.summary_lines()]
        if receipt.confidence < settings.confidence_warn_threshold:
            lines.append("⚠ 読み取りに自信がありません。内容をよく確認してください。")
            if receipt.notes:
                lines.append(f"({receipt.notes})")
        lines.append("この内容で登録しますか?")
        try:
            line.reply_confirm(reply_token, "\n".join(lines), token)
        except Exception:
            logger.exception("failed to send confirm for %s", message_id)

    def handle_postback(data: str, reply_token: str) -> None:
        params = parse_qs(data)
        action = (params.get("action") or [""])[0]
        token = (params.get("token") or [""])[0]
        receipt = store.pop_pending(token)
        if receipt is None:
            line.reply_text(reply_token, "この確認は期限切れか、すでに処理済みです。")
            return
        if action != "confirm":
            line.reply_text(reply_token, "登録をキャンセルしました。")
            return
        try:
            result = registrar.register(receipt)
        except Exception:
            logger.exception("register failed")
            line.reply_text(
                reply_token, "マネーフォワードへの登録に失敗しました。時間をおいて再送してください。"
            )
            return
        line.reply_text(reply_token, f"✅ {result}")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/callback")
    async def callback(
        request: Request,
        background: BackgroundTasks,
        x_line_signature: str = Header(default=""),
    ) -> dict:
        body = await request.body()
        if not verify_signature(settings.line_channel_secret, body, x_line_signature):
            raise HTTPException(status_code=403, detail="invalid signature")

        payload = await request.json()
        for event in payload.get("events", []):
            etype = event.get("type")
            reply_token = event.get("replyToken", "")
            if etype == "message" and event.get("message", {}).get("type") == "image":
                # LINEには即200を返し、重い処理(画像取得・OpenAI呼び出し)は裏で行う
                background.add_task(
                    handle_image, event["message"]["id"], reply_token
                )
            elif etype == "postback":
                background.add_task(
                    handle_postback, event.get("postback", {}).get("data", ""), reply_token
                )
        return {"status": "ok"}

    return app


app = create_app()
