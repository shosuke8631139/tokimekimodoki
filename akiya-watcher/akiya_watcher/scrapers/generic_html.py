"""設定駆動の汎用HTMLアダプタ。

自治体の空き家バンクは市町村ごとにHTML構造が違うが、多くは
「一覧ページに物件カードが並び、カード内に価格・所在地・リンクがある」
という同型の構造をしている。そこでセレクタを config.yaml 側に持たせ、
コードを書かずにソースを追加できるようにする。

config.yaml の sources 例:
    - id: kagoshima_city_akiya
      type: generic_html
      list_url: "https://example.jp/akiya/list"
      item_selector: "div.property-card"
      fields:
        title:   {selector: "h3 a", attr: "text"}
        url:     {selector: "h3 a", attr: "href"}
        price:   {selector: ".price", attr: "text"}
        address: {selector: ".address", attr: "text"}
        layout:  {selector: ".layout", attr: "text"}
        description: {selector: ".note", attr: "text"}

※ 実サイトのセレクタは各自でブラウザの開発者ツールで確認して設定すること。
   また対象サイトの利用規約・robots.txt を必ず確認すること。
"""
from __future__ import annotations

import hashlib
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..criteria import parse_area_sqm, parse_parking_slots, parse_price_yen
from ..models import Listing
from .base import BaseScraper


class GenericHtmlScraper(BaseScraper):
    source_id = "generic_html"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config["id"]
        self.list_url = config["list_url"]
        self.item_selector = config["item_selector"]
        self.fields: dict = config.get("fields", {})

    def _extract(self, node, spec: dict) -> str:
        el = node.select_one(spec["selector"]) if spec.get("selector") else node
        if el is None:
            return ""
        attr = spec.get("attr", "text")
        if attr == "text":
            return el.get_text(" ", strip=True)
        return el.get(attr, "")

    def fetch_listings(self) -> list[Listing]:
        res = self.get(self.list_url)
        soup = BeautifulSoup(res.text, "html.parser")
        listings: list[Listing] = []
        for node in soup.select(self.item_selector):
            f = {name: self._extract(node, spec) for name, spec in self.fields.items()}
            url = urljoin(self.list_url, f.get("url", ""))
            # ID列がないサイトが多いのでURL(なければ内容)から安定IDを作る
            id_basis = url or (f.get("title", "") + f.get("address", ""))
            listing_id = hashlib.sha256(id_basis.encode("utf-8")).hexdigest()[:16]
            text_blob = " ".join(f.values())
            listings.append(Listing(
                source=self.source_id,
                listing_id=listing_id,
                title=f.get("title", "(無題)"),
                url=url,
                price_yen=parse_price_yen(f.get("price", "")),
                address=f.get("address", ""),
                floor_area_sqm=parse_area_sqm(f.get("floor_area", "")),
                land_area_sqm=parse_area_sqm(f.get("land_area", "")),
                layout=f.get("layout", ""),
                parking_slots=parse_parking_slots(text_blob),
                toilet=f.get("toilet", ""),
                description=f.get("description", ""),
                raw=f,
            ))
        return listings
