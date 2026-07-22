"""SQLite による永続化。

- processed_messages: LINEメッセージIDの冪等性担保(同じ画像の二重処理防止)
- pending: 承認待ちの読み取り結果(トークン→Receipt)
"""

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Receipt


class Store:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = data_dir / "keihi-bot.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS processed_messages (
                       message_id TEXT PRIMARY KEY,
                       processed_at TEXT NOT NULL
                   )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS pending (
                       token TEXT PRIMARY KEY,
                       receipt_json TEXT NOT NULL,
                       created_at TEXT NOT NULL
                   )"""
            )

    def mark_processed(self, message_id: str) -> bool:
        """未処理なら記録して True。処理済みなら False(スキップすべき)。"""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
                    (message_id, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def save_pending(self, receipt: Receipt) -> str:
        token = secrets.token_urlsafe(12)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pending (token, receipt_json, created_at) VALUES (?, ?, ?)",
                (token, receipt.model_dump_json(), now),
            )
        return token

    def pop_pending(self, token: str) -> Optional[Receipt]:
        """承認/却下時に取り出して削除する(二度押し対策も兼ねる)。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_json FROM pending WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                return None
            conn.execute("DELETE FROM pending WHERE token = ?", (token,))
        return Receipt(**json.loads(row[0]))
