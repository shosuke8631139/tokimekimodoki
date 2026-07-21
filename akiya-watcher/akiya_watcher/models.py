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
class ListingContext:
    """差分DBから得た、スコアリングに使う履歴情報。"""
    is_new: bool = True
    age_days: int = 0                      # 初回掲載からの経過日数
    previous_price_yen: int | None = None  # 直前の(現在と異なる)価格
    current_price_yen: int | None = None
    price_changed: bool = False

    @property
    def drop_pct(self) -> int | None:
        """値下げ率(%)。値下げでなければ None。"""
        if (self.previous_price_yen and self.current_price_yen is not None
                and self.current_price_yen < self.previous_price_yen):
            return round(100 * (self.previous_price_yen - self.current_price_yen)
                         / self.previous_price_yen)
        return None


@dataclass
class Score:
    """スコアリング結果。落とさない——全物件がスコア順に並ぶ。"""
    total: int = 0
    badges: list[str] = field(default_factory=list)    # レポートに出す短いラベル
    reasons: list[str] = field(default_factory=list)   # 加点・減点の内訳
    unknowns: list[str] = field(default_factory=list)  # 記載がなく要確認の項目
    matched_keywords: list[str] = field(default_factory=list)

    def add(self, points: int, reason: str, badge: str | None = None) -> None:
        self.total += points
        sign = "+" if points >= 0 else ""
        self.reasons.append(f"{reason} ({sign}{points})")
        if badge:
            self.badges.append(badge)
