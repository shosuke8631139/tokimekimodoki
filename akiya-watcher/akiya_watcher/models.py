"""物件データモデル。

各スクレイパーはサイト固有のHTMLをこの共通モデルに正規化して返す。
判定・保存・通知はすべて Listing だけを扱い、サイト構造の差異を隔離する。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Listing:
    source: str                      # 情報源ID (例: "demo", "akiya_athome")
    listing_id: str                  # 情報源内で一意なID
    title: str
    url: str
    price_yen: int | None = None     # 円。不明は None
    address: str = ""
    floor_area_sqm: float | None = None   # 延床面積
    land_area_sqm: float | None = None    # 敷地面積
    layout: str = ""                 # 間取り表記 (例: "4LDK")
    parking_slots: int | None = None      # 駐車可能台数。不明は None
    toilet: str = ""                 # トイレ/排水の記載 (例: "水洗(浄化槽)")
    description: str = ""            # 備考・特記事項などの自由文
    raw: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.listing_id}"

    def content_hash(self) -> str:
        """価格・本文の変化検知用ハッシュ。"""
        basis = f"{self.price_yen}|{self.title}|{self.description}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()


@dataclass
class Judgement:
    """判定結果。matched=True の物件だけが通知対象。"""
    matched: bool
    score: int                       # 条件合致度 (通知の優先度表示に使用)
    matched_keywords: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)      # 合致した理由
    disqualifiers: list[str] = field(default_factory=list)  # 不合致の理由
