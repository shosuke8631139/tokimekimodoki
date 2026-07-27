"""追跡リスト (ユーザー指名物件のページ直接ウォッチ)。

「この物件を追っかけて」と指名された個別ページを毎回の巡回で直接見に行き、
価格・記載の変化と掲載終了を検知する。指名物件は自動でキープ(⭐)扱いになり、
エリア・価格の足切りも通らない (指名した本人の意思が最優先)。

config 例:
  - id: watchlist
    type: watch
    enabled: true
    entries:
      - url: "https://akiya.sumai.biz/117604"
        note: "ユーザー指名 2026-07-24"
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..criteria import parse_price_yen
from ..models import Listing
from .base import BaseScraper

TITLE_PAT = re.compile(r"<title>(.*?)</title>", re.S)
OG_PAT = 'property="{prop}" content="([^"]*)"'
# 掲載が生きていないことを示す表現 (ページが200のまま終了するサイト対策)
GONE_PAT = re.compile(r"成約済|成約しました|掲載終了|掲載を終了|募集終了|見つかりません")
ADDRESS_PAT = re.compile(r"([一-龥]{2,4}[都道府県][^\s　【】()()]+)")
PRICE_NEAR_PAT = re.compile(r"[0-9,]+(?:\.[0-9]+)?\s*(?:億[0-9,]*)?万円")


def _og(html: str, prop: str) -> str:
    m = re.search(f'property="{prop}"\\s+content="([^"]*)"', html)
    if not m:
        m = re.search(f'content="([^"]*)"\\s+property="{prop}"', html)
    return m.group(1) if m else ""


def parse_watch_page(url: str, html: str) -> Listing | None:
    """指名物件ページを Listing に変換する。掲載終了とみなせるページは None。"""
    title = _og(html, "og:title")
    if not title:
        m = TITLE_PAT.search(html)
        title = " ".join(m.group(1).split()) if m else url
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    if GONE_PAT.search(text[:3000]) and not PRICE_NEAR_PAT.search(title):
        return None
    price = parse_price_yen(title)
    if price is None:
        m = PRICE_NEAR_PAT.search(text)
        price = parse_price_yen(m.group(0)) if m else None
    am = ADDRESS_PAT.search(title) or ADDRESS_PAT.search(text)
    desc = _og(html, "og:description") or text[:800]
    listing_id = urlparse(url).path.strip("/") or url
    return Listing(
        source="watch", listing_id=listing_id, title=f"⭐追跡: {title}"[:120],
        url=url, price_yen=price, address=am.group(1) if am else "",
        description=desc[:1500],
    )


class WatchScraper(BaseScraper):
    source_id = "watch"
    full_snapshot = True   # entries が全量。見えなくなったら掲載終了扱い
    prices_reliable = False  # 本文からの推定なので None を応相談と断定しない
    always_keep = True     # 指名物件は常に⭐キープ・足切り免除

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        for entry in self.config.get("entries", []):
            url = entry.get("url", "").strip()
            if not url:
                continue
            try:
                res = self.get(url)
            except Exception as e:
                # 404等 = 掲載終了の可能性。リストから消えれば delisted 扱いになる
                print(f"[warn] watchlist: {url} 取得できず ({type(e).__name__}: {e})")
                continue
            ls = parse_watch_page(url, res.text)
            if ls is None:
                print(f"[info] watchlist: {url} は掲載終了の表示")
                continue
            if entry.get("note"):
                ls.description = f"({entry['note']}) {ls.description}"[:1500]
            listings.append(ls)
        return listings
