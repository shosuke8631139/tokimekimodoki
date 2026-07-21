"""RSSフィードアダプタ。

Sumai空き家 (akiya.sumai.biz) はWordPressのRSSを公式に公開しており、
新着・価格変更の投稿がタイトルつきで配信される。robots.txt も許可を確認済み
(2026-07 接続テスト)。サイトが用意した配信を受け取るだけなので最も行儀が良い。

タイトルは「空き家バンク【売買】230万円 鹿児島県鹿屋市永野田町 …」形式で、
sumai_akiya の parse_listing_title がそのまま使える。リサーチ範囲外の県は
collect() の target_areas フィルタが落とす。
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urlunparse

from ..models import Listing
from .base import BaseScraper
from .sumai_akiya import parse_listing_title


class RssScraper(BaseScraper):
    source_id = "rss"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", "rss")
        self.feed_urls: list[str] = config.get("feed_urls", [])

    def _canonical(self, url: str) -> str:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

    def fetch_listings(self) -> list[Listing]:
        found: dict[str, Listing] = {}
        for feed_url in self.feed_urls:
            try:
                res = self.get(feed_url)
                root = ET.fromstring(res.content)
            except Exception as e:
                print(f"[warn] {self.source_id}: フィード取得失敗 {feed_url} - {e}")
                continue
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                parsed = parse_listing_title(title)
                if parsed is None or not link:
                    continue
                canon = self._canonical(link)
                if canon in found:
                    continue
                found[canon] = Listing(
                    source=self.source_id,
                    listing_id=hashlib.sha256(canon.encode()).hexdigest()[:16],
                    title=parsed["title"][:200],
                    url=link,
                    price_yen=parsed["price_yen"],
                    address=parsed["address"],
                    description=parsed["title"],
                    advertised_previous_price_yen=parsed["advertised_previous_price_yen"],
                    raw={"canonical_url": canon, "feed": feed_url},
                )
        return found and list(found.values()) or []
