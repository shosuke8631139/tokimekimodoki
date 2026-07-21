"""SQLite による既知物件の記録・価格履歴・差分検知。

「値下げの瞬間」を捉えることがこのツールの存在理由なので、価格は履歴として
すべて保存し、掲載期間 (first_seen からの経過日数) も追跡する。
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Listing, ListingContext

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    uid          TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    listing_id   TEXT NOT NULL,
    url          TEXT,
    title        TEXT,
    price_yen    INTEGER,
    content_hash TEXT,
    first_seen   INTEGER,
    last_seen    INTEGER
);
CREATE TABLE IF NOT EXISTS price_history (
    uid       TEXT NOT NULL,
    price_yen INTEGER,
    seen_at   INTEGER NOT NULL
);
"""


@dataclass
class Diff:
    kind: str                    # "new" | "changed" | "unchanged"
    listing: Listing
    context: ListingContext


class Store:
    def __init__(self, path: str | Path, now: int | None = None):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._now = now  # テスト用に固定時刻を注入できる

    def now(self) -> int:
        return self._now if self._now is not None else int(time.time())

    def close(self) -> None:
        self.conn.close()

    def upsert(self, ls: Listing) -> Diff:
        """物件を記録し、履歴コンテキストつきの差分を返す。"""
        now = self.now()
        new_hash = ls.content_hash()
        row = self.conn.execute(
            "SELECT price_yen, content_hash, first_seen FROM listings WHERE uid = ?",
            (ls.uid,),
        ).fetchone()

        if row is None:
            self.conn.execute(
                "INSERT INTO listings (uid, source, listing_id, url, title,"
                " price_yen, content_hash, first_seen, last_seen)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (ls.uid, ls.source, ls.listing_id, ls.url, ls.title,
                 ls.price_yen, new_hash, now, now),
            )
            self.conn.execute(
                "INSERT INTO price_history (uid, price_yen, seen_at) VALUES (?, ?, ?)",
                (ls.uid, ls.price_yen, now),
            )
            self.conn.commit()
            ctx = ListingContext(is_new=True, age_days=0,
                                 current_price_yen=ls.price_yen)
            return Diff(kind="new", listing=ls, context=ctx)

        old_price, old_hash, first_seen = row
        self.conn.execute(
            "UPDATE listings SET url=?, title=?, price_yen=?, content_hash=?,"
            " last_seen=? WHERE uid=?",
            (ls.url, ls.title, ls.price_yen, new_hash, now, ls.uid),
        )
        price_changed = old_price != ls.price_yen
        if price_changed:
            self.conn.execute(
                "INSERT INTO price_history (uid, price_yen, seen_at) VALUES (?, ?, ?)",
                (ls.uid, ls.price_yen, now),
            )
        self.conn.commit()

        # 直前の「現在と異なる」価格を履歴から取る (値下げ率の計算用)
        prev = self.conn.execute(
            "SELECT price_yen FROM price_history WHERE uid=? AND price_yen IS NOT NULL"
            " AND price_yen != ? ORDER BY seen_at DESC LIMIT 1",
            (ls.uid, ls.price_yen if ls.price_yen is not None else -1),
        ).fetchone()
        ctx = ListingContext(
            is_new=False,
            age_days=max(0, (now - first_seen) // 86400),
            previous_price_yen=prev[0] if prev else None,
            current_price_yen=ls.price_yen,
            price_changed=price_changed,
        )
        kind = "changed" if old_hash != new_hash else "unchanged"
        return Diff(kind=kind, listing=ls, context=ctx)
