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

from .models import Score
from .storage import Diff


def format_message(diff: Diff, score: Score) -> str:
    ls, ctx = diff.listing, diff.context
    if ctx.price_changed and ctx.drop_pct:
        head = f"🔻 値下げ検知 (▼{ctx.drop_pct}%)"
    elif diff.kind == "new":
        head = "🆕 新着物件"
    else:
        head = "🔄 掲載変更"
    price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格不明(指値候補)"
    if ctx.drop_pct and ctx.previous_price_yen:
        price = f"{ctx.previous_price_yen:,}円 → {price}"
    lines = [
        f"{head} [score {score.total}]",
        f"物件名: {ls.title}",
        f"価格: {price}",
        f"所在地: {ls.address or '不明'}",
        f"シグナル: {' '.join(score.badges) or 'なし'}",
        f"要確認: {'、'.join(score.unknowns) or 'なし'}",
        f"URL: {ls.url}",
    ]
    return "\n".join(lines)


class Notifier:
    def __init__(self, slack_webhook_url: str | None = None):
        self.webhook = slack_webhook_url or os.environ.get("SLACK_WEBHOOK_URL")

    def send(self, diff: Diff, score: Score) -> None:
        self.send_text(format_message(diff, score))

    def send_text(self, text: str) -> None:
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
