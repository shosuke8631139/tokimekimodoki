"""通知モジュール。

2つのチャンネルに対応:
  - メール(自分宛てGmail): Gmail連携と同じアプリパスワードで送れるので、
    追加のアカウント登録が一切不要。スマホのGmail通知がそのまま鳴る。
  - Slack Incoming Webhook: Slackを使っている人向け。

どちらも未設定なら標準出力に出す(動作確認・cron ログ用)。
LINE Notify は 2025年3月末でサービス終了したため対応しない。
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage

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
    """設定されている全チャンネルへ送る。未設定なら標準出力。

    email 設定例 (config.yaml の notify.email):
        username: your-address@gmail.com   # 送信元 = 宛先 (自分宛て)
        password_env: GMAIL_APP_PASSWORD   # Gmail連携と同じアプリパスワード
    """

    def __init__(self, slack_webhook_url: str | None = None,
                 email: dict | None = None):
        self.webhook = slack_webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self.email = email if email and email.get("username") else None

    def send(self, diff: Diff, score: Score) -> None:
        self.send_text(format_message(diff, score))

    def send_text(self, text: str) -> None:
        sent = False
        if self.webhook:
            self._send_slack(text)
            sent = True
        if self.email:
            self._send_mail(text)
            sent = True
        if not sent:
            print("---- 通知 (通知先未設定のため標準出力) ----")
            print(text)

    def _send_slack(self, text: str) -> None:
        payload = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            self.webhook, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            res.read()

    def _send_mail(self, text: str) -> None:
        username = self.email["username"]
        password = os.environ.get(self.email.get("password_env", "GMAIL_APP_PASSWORD"))
        if not password:
            print("[warn] メール通知: アプリパスワード未設定のためスキップ")
            return
        msg = EmailMessage()
        # 件名 = 本文の1行目 (例: "🔻 値下げ検知 (▼67%) [score 29]")
        msg["Subject"] = text.splitlines()[0][:80]
        msg["From"] = username
        msg["To"] = self.email.get("to", username)
        msg.set_content(text)
        host = self.email.get("smtp_host", "smtp.gmail.com")
        with smtplib.SMTP_SSL(host, self.email.get("smtp_port", 465),
                              timeout=20) as smtp:
            smtp.login(username, password)
            smtp.send_message(msg)
