"""SQLite による既知物件の記録と差分検知。

- 初見の物件           → "new"
- 価格・本文が変わった物件 → "changed" (旧価格を添えて返す)
- 変化なし             → 通知しない
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Listing

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
"""


@dataclass
class Diff:
    kind: str                    # "new" | "changed"
    listing: Listing
    old_price_yen: int | None = None


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def upsert(self, ls: Listing) -> Diff | None:
        """物件を記録し、通知すべき差分があれば返す。"""
        now = int(time.time())
        new_hash = ls.content_hash()
        row = self.conn.execute(
            "SELECT price_yen, content_hash FROM listings WHERE uid = ?",
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
            self.conn.commit()
            return Diff(kind="new", listing=ls)

        old_price, old_hash = row
        self.conn.execute(
            "UPDATE listings SET url=?, title=?, price_yen=?, content_hash=?,"
            " last_seen=? WHERE uid=?",
            (ls.url, ls.title, ls.price_yen, new_hash, now, ls.uid),
        )
        self.conn.commit()
        if old_hash != new_hash:
            return Diff(kind="changed", listing=ls, old_price_yen=old_price)
        return None
