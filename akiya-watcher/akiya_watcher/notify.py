"""通知モジュール。

Slack Incoming Webhook に整形メッセージを送る。Webhook 未設定時は標準出力に
同じ内容を出す(動作確認・cron ログ用)。

LINE Notify は 2025年3月末でサービス終了したため対応しない。LINE に送りたい
場合は LINE Messaging API (Push Message) 用の Notifier をここに追加する。
"""
from __future__ import annotations

import json
import os
import urllib.request

from .models import Judgement, Listing
from .storage import Diff


def format_message(diff: Diff, judgement: Judgement) -> str:
    ls = diff.listing
    head = "🆕 新着お宝候補" if diff.kind == "new" else "🔄 掲載変更(価格改定?)"
    price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格不明"
    if diff.kind == "changed" and diff.old_price_yen and diff.old_price_yen != ls.price_yen:
        price = f"{diff.old_price_yen:,}円 → {price}"
    parking = f"{ls.parking_slots}台" if ls.parking_slots is not None else "記載なし(本文参照)"
    kw = "、".join(judgement.matched_keywords) or "なし"
    lines = [
        f"{head} [score {judgement.score}]",
        f"物件名: {ls.title}",
        f"価格: {price}",
        f"所在地: {ls.address or '不明'}",
        f"駐車場: {parking}",
        f"該当キーワード: {kw}",
        f"判定理由: {' / '.join(judgement.reasons)}",
        f"URL: {ls.url}",
    ]
    return "\n".join(lines)


class Notifier:
    def __init__(self, slack_webhook_url: str | None = None):
        self.webhook = slack_webhook_url or os.environ.get("SLACK_WEBHOOK_URL")

    def send(self, diff: Diff, judgement: Judgement) -> None:
        text = format_message(diff, judgement)
        if not self.webhook:
            print("---- 通知 (SLACK_WEBHOOK_URL 未設定のため標準出力) ----")
            print(text)
            return
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self.webhook, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            res.read()
