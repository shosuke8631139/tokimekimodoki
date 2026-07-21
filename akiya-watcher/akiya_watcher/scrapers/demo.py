"""ローカルのサンプルJSONを読むデモアダプタ。

ネットワーク不要でパイプライン全体(取得→判定→差分→通知)を動かすための
情報源。実サイトを追加する前の動作確認や、判定条件のチューニングに使う。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..criteria import parse_area_sqm, parse_parking_slots, parse_price_yen
from ..models import Listing
from .base import BaseScraper


class DemoScraper(BaseScraper):
    source_id = "demo"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", "demo")
        self.path = Path(config["path"])

    def fetch_listings(self) -> list[Listing]:
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        listings = []
        for row in rows:
            listings.append(Listing(
                source=self.source_id,
                listing_id=str(row["id"]),
                title=row.get("title", ""),
                url=row.get("url", ""),
                price_yen=parse_price_yen(str(row.get("price", ""))),
                address=row.get("address", ""),
                floor_area_sqm=parse_area_sqm(str(row.get("floor_area", ""))),
                land_area_sqm=parse_area_sqm(str(row.get("land_area", ""))),
                layout=row.get("layout", ""),
                parking_slots=parse_parking_slots(str(row.get("parking", ""))),
                toilet=row.get("toilet", ""),
                description=row.get("description", ""),
                raw=row,
            ))
        return listings
