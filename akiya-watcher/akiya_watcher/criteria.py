"""探索ターゲット条件の判定ロジック。

物件表記の揺れ(「198万円」「1,980,000円」「駐車2台可」「並列3台」等)を
正規化するパーサ群と、config.yaml の条件で Listing を判定する Judge を提供する。
すべて純関数/純クラスなのでオフラインで単体テストできる。
"""
from __future__ import annotations

import re
import unicodedata

from .models import Judgement, Listing

# ---------------------------------------------------------------- パーサ群


def _normalize(text: str) -> str:
    """全角数字・記号を半角へ、空白を除去して表記揺れを吸収する。"""
    return unicodedata.normalize("NFKC", text or "").replace(" ", "").replace("　", "")


def parse_price_yen(text: str) -> int | None:
    """価格表記を円に変換する。例: "198万円"→1980000, "1,980,000円"→1980000。"""
    t = _normalize(text)
    if not t:
        return None
    m = re.search(r"([0-9,]+(?:\.[0-9]+)?)億", t)
    oku = float(m.group(1).replace(",", "")) if m else 0.0
    rest = t[m.end():] if m else t
    m = re.search(r"([0-9,]+(?:\.[0-9]+)?)万", rest)
    if m or oku:
        man = float(m.group(1).replace(",", "")) if m else 0.0
        return int(oku * 100_000_000 + man * 10_000)
    m = re.search(r"([0-9,]{4,})円?", t)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def parse_area_sqm(text: str) -> float | None:
    """面積表記を㎡に変換する。例: "103.5㎡", "延床120m2", "80平米"。"""
    t = _normalize(text)
    m = re.search(r"([0-9,]+(?:\.[0-9]+)?)(?:㎡|m2|平米|平方メートル)", t, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def parse_layout_rooms(layout: str) -> int | None:
    """間取り表記から居室数を取り出す。例: "4LDK"→4, "5DK+S"→5。"""
    t = _normalize(layout)
    m = re.search(r"([0-9]+)\s*(?:S?LDK|LDK|DK|K|R)", t, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_parking_slots(text: str) -> int | None:
    """駐車場の記載から駐車可能台数を推定する。

    "駐車場:3台"「並列2台可」「駐車スペース2台分」などを拾う。
    「駐車場あり」だけなら 1 台とみなす。記載がなければ None。
    """
    t = _normalize(text)
    if not t:
        return None
    best: int | None = None
    for m in re.finditer(r"(?:駐車|カースペース|ガレージ|車庫)[^0-9台]{0,12}([0-9]+)台", t):
        n = int(m.group(1))
        best = n if best is None else max(best, n)
    if best is None:
        for m in re.finditer(r"(?:並列|縦列)([0-9]+)台", t):
            n = int(m.group(1))
            best = n if best is None else max(best, n)
    if best is None and re.search(r"駐車場?(?:あり|有り?|付き?)", t):
        best = 1
    return best


FLUSH_TOILET_PAT = re.compile(r"水洗|下水道?|公共下水|浄化槽")
NON_FLUSH_PAT = re.compile(r"汲み?取り?|くみ取り?|簡易水洗")


def is_flush_toilet(text: str) -> bool | None:
    """水洗トイレ(公共下水・浄化槽)かどうか。判別不能なら None。

    「簡易水洗」は実態が汲み取りなので水洗とはみなさない。
    """
    t = _normalize(text)
    if not t:
        return None
    if NON_FLUSH_PAT.search(t):
        return False
    if FLUSH_TOILET_PAT.search(t):
        return True
    return None

# ---------------------------------------------------------------- 判定


DEFAULT_KEYWORDS = [
    "残置物",
    "現状渡し",
    "現状引き渡し",
    "現状有姿",
    "未片付け",
    "家具",
    "家財",
    "要補修",
    "要修繕",
    "要リフォーム",
    "古家",
    "解体前提",
]


class Judge:
    """config の条件で Listing を判定する。

    criteria 例 (config.yaml の criteria セクション):
        price_max_yen: 2000000
        parking_min_slots: 2
        land_area_fallback_sqm: 200   # 駐車場記載なしでも敷地がこれ以上なら可
        floor_area_min_sqm: 80
        rooms_min: 4                  # 4LDK 以上
        keywords: [残置物, 現状渡し, ...]
        require_flush_toilet: true
        priority_cities: [鹿児島市, 霧島市, 薩摩川内市, 鹿屋市]
    """

    def __init__(self, criteria: dict):
        self.price_max = criteria.get("price_max_yen", 2_000_000)
        self.parking_min = criteria.get("parking_min_slots", 2)
        self.land_fallback = criteria.get("land_area_fallback_sqm", 200)
        self.floor_min = criteria.get("floor_area_min_sqm", 80)
        self.rooms_min = criteria.get("rooms_min", 4)
        self.keywords = criteria.get("keywords") or DEFAULT_KEYWORDS
        self.require_flush = criteria.get("require_flush_toilet", True)
        self.priority_cities = criteria.get("priority_cities", [])

    def judge(self, ls: Listing) -> Judgement:
        reasons: list[str] = []
        disq: list[str] = []
        score = 0
        blob = " ".join([ls.title, ls.description, ls.toilet, ls.layout])

        # 価格 (不明は「大幅指値候補」として残し、明確な超過だけ弾く)
        if ls.price_yen is None:
            reasons.append("価格不明(要確認・指値候補)")
        elif ls.price_yen <= self.price_max:
            reasons.append(f"価格 {ls.price_yen:,}円 ≤ 上限 {self.price_max:,}円")
            score += 2
        else:
            disq.append(f"価格 {ls.price_yen:,}円 が上限超過")

        # 駐車場 (台数記載がなければ敷地面積でフォールバック)
        slots = ls.parking_slots
        if slots is None:
            slots = parse_parking_slots(blob)
        if slots is not None and slots >= self.parking_min:
            reasons.append(f"駐車 {slots}台 ≥ {self.parking_min}台")
            score += 2
        elif ls.land_area_sqm and ls.land_area_sqm >= self.land_fallback:
            reasons.append(f"敷地 {ls.land_area_sqm}㎡ ≥ {self.land_fallback}㎡(駐車余地)")
            score += 1
        else:
            disq.append(f"駐車{self.parking_min}台の確証なし")

        # 建物規模 (延床 or 間取りのどちらかを満たせばよい)
        rooms = parse_layout_rooms(ls.layout)
        if ls.floor_area_sqm and ls.floor_area_sqm >= self.floor_min:
            reasons.append(f"延床 {ls.floor_area_sqm}㎡ ≥ {self.floor_min}㎡")
            score += 1
        elif rooms is not None and rooms >= self.rooms_min:
            reasons.append(f"間取り {ls.layout} ({rooms}室 ≥ {self.rooms_min}室)")
            score += 1
        else:
            disq.append(f"延床{self.floor_min}㎡以上/{self.rooms_min}LDK以上の確証なし")

        # お宝キーワード
        matched_kw = [kw for kw in self.keywords if kw in blob]
        if matched_kw:
            reasons.append("キーワード: " + "、".join(matched_kw))
            score += len(matched_kw)

        # トイレ
        flush = is_flush_toilet(ls.toilet or blob)
        if flush is True:
            reasons.append("水洗トイレ")
            score += 1
        elif flush is False:
            if self.require_flush:
                disq.append("汲み取り式(水洗必須条件)")
            else:
                reasons.append("汲み取り式(要改修コスト)")
        else:
            reasons.append("トイレ形式不明(要確認)")

        # 優先エリア加点
        if any(city in ls.address for city in self.priority_cities):
            score += 1
            reasons.append("優先エリア")

        matched = not disq
        return Judgement(matched=matched, score=score,
                         matched_keywords=matched_kw,
                         reasons=reasons, disqualifiers=disq)
