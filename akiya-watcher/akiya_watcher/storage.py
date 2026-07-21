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
    last_seen    INTEGER,
    delisted_at  INTEGER
);
CREATE TABLE IF NOT EXISTS price_history (
    uid       TEXT NOT NULL,
    price_yen INTEGER,
    seen_at   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS deals (
    uid        TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    offer_yen  INTEGER,
    note       TEXT,
    updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS deal_log (
    uid       TEXT NOT NULL,
    status    TEXT NOT NULL,
    offer_yen INTEGER,
    note      TEXT,
    at        INTEGER NOT NULL
);
"""

# 商談ステータス (番号は deals CLI の選択肢)
DEAL_STATUSES = ["気になる", "問い合わせ済", "内見済", "指値中", "成約", "見送り"]


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
        # 既存DBへの後付けマイグレーション
        for migration in (
            "ALTER TABLE listings ADD COLUMN delisted_at INTEGER",
            "ALTER TABLE listings ADD COLUMN is_keep INTEGER DEFAULT 0",
        ):
            try:
                self.conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # 既にある
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
            " last_seen=?, delisted_at=NULL WHERE uid=?",
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

    def finalize_crawl(self, source: str, seen_uids: set[str]) -> list[str]:
        """一覧型ソースの巡回後に呼ぶ。今回見えなかった物件を掲載終了とみなす。

        掲載終了 ≒ 売れた(または取り下げ)。市場のスピード感を学ぶ材料になる。
        メール型ソース(メールに出ない=終了ではない)には使わないこと。
        戻り値は今回掲載終了になった uid のリスト。
        """
        now = self.now()
        rows = self.conn.execute(
            "SELECT uid FROM listings WHERE source=? AND delisted_at IS NULL",
            (source,),
        ).fetchall()
        gone = [uid for (uid,) in rows if uid not in seen_uids]
        for uid in gone:
            self.conn.execute(
                "UPDATE listings SET delisted_at=? WHERE uid=?", (now, uid))
        self.conn.commit()
        return gone

    def set_keep(self, uid: str, keep: bool) -> None:
        """⭐キープ(理想条件合致)の印を付ける。掲載終了通知の判定に使う。"""
        self.conn.execute("UPDATE listings SET is_keep=? WHERE uid=?",
                          (1 if keep else 0, uid))
        self.conn.commit()

    def listing_info(self, uid: str) -> dict | None:
        row = self.conn.execute(
            "SELECT title, url, price_yen, is_keep FROM listings WHERE uid=?",
            (uid,)).fetchone()
        if row is None:
            return None
        return {"title": row[0], "url": row[1], "price_yen": row[2],
                "is_keep": bool(row[3])}

    def set_deal(self, uid: str, status: str, offer_yen: int | None = None,
                 note: str = "") -> None:
        """商談状態を更新し、履歴(実戦データ)にも積む。"""
        now = self.now()
        self.conn.execute(
            "INSERT INTO deals (uid, status, offer_yen, note, updated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(uid) DO UPDATE SET status=excluded.status,"
            " offer_yen=excluded.offer_yen, note=excluded.note,"
            " updated_at=excluded.updated_at",
            (uid, status, offer_yen, note, now))
        self.conn.execute(
            "INSERT INTO deal_log (uid, status, offer_yen, note, at)"
            " VALUES (?, ?, ?, ?, ?)", (uid, status, offer_yen, note, now))
        self.conn.commit()

    def deals(self) -> dict[str, dict]:
        """uid → 商談状態。レポートのバッジ表示に使う。"""
        rows = self.conn.execute(
            "SELECT uid, status, offer_yen, note FROM deals").fetchall()
        return {u: {"status": s, "offer_yen": o, "note": n}
                for u, s, o, n in rows}

    def deal_history(self) -> list[dict]:
        """実戦データ: 指値・成約・見送りの全履歴 (物件情報つき・新しい順)。"""
        rows = self.conn.execute(
            "SELECT g.uid, g.status, g.offer_yen, g.note, g.at,"
            " l.title, l.price_yen, l.url"
            " FROM deal_log g LEFT JOIN listings l ON l.uid = g.uid"
            " ORDER BY g.at DESC, g.rowid DESC").fetchall()
        return [{"uid": u, "status": s, "offer_yen": o, "note": n, "at": a,
                 "title": t or u, "price_yen": p, "url": url or ""}
                for u, s, o, n, a, t, p, url in rows]

    def recent_listings(self, limit: int = 40) -> list[dict]:
        """商談ノートCLIで選ぶための物件一覧 (掲載中を新しい順)。"""
        rows = self.conn.execute(
            "SELECT uid, title, price_yen, url FROM listings"
            " WHERE delisted_at IS NULL ORDER BY last_seen DESC, first_seen DESC"
            " LIMIT ?", (limit,)).fetchall()
        return [{"uid": u, "title": t, "price_yen": p, "url": url}
                for u, t, p, url in rows]

    def recent_delisted(self, within_days: int = 30) -> list[dict]:
        """最近掲載終了した物件 (売れた実績データ)。新しい順。"""
        cutoff = self.now() - within_days * 86400
        rows = self.conn.execute(
            "SELECT title, url, price_yen, first_seen, delisted_at, source"
            " FROM listings WHERE delisted_at IS NOT NULL AND delisted_at >= ?"
            " ORDER BY delisted_at DESC",
            (cutoff,),
        ).fetchall()
        return [{
            "title": t, "url": u, "price_yen": p,
            "days_on_market": max(0, (d - f) // 86400),
            "source": s,
        } for t, u, p, f, d, s in rows]
