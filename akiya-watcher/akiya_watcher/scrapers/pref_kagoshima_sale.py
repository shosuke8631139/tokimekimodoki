"""鹿児島県 県有財産売却 (売却中の物件明細) アダプタ。

2026-08-09 偵察結果 (Actions run 31315669435) に基づく:
  - 「売却中の物件明細」ページに、旧教職員住宅・旧警察署跡地などの
    物件明細リンク (bukenholder/ 配下) が並ぶ。随時受付の売り払いもあり、
    公売と違って入札期日に縛られない出物が混ざる。
  - 価格・所在地は明細ページやPDF側にあり一覧には無い。ここでは
    「何が売りに出たか」の検知に徹する (prices_reliable=False)。
  - 県サイトはcharset宣言が実体とずれることがあるため、バイト列から
    BeautifulSoupに文字コードを判定させる (res.text は文字化けする)。
  - robots.txt は /kojisotatsu/ のみ不許可でこのページは対象外。

一覧は「現在売却中の全物件」なので full_snapshot=True。
リンクが消えた = 売れた/取り下げの検知として意味を持つ。
"""
from __future__ import annotations

import hashlib
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

LIST_URL = "https://www.pref.kagoshima.jp/kensei/nyusatu/zaisan/bukken/index.html"


class PrefKagoshimaSaleScraper(BaseScraper):
    source_id = "kagoshima_pref_sale"
    full_snapshot = True
    prices_reliable = False   # 価格は明細/PDF側。Noneを応相談カットさせない

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config["id"]
        self.list_url = config.get("list_url", LIST_URL)

    def fetch_listings(self) -> list[Listing]:
        res = self.get(self.list_url)
        # res.text は宣言charsetのずれで化けるため、バイト列から判定させる
        return self.parse_index(res.content, self.list_url, self.source_id)

    @classmethod
    def parse_index(cls, content: bytes | str, base_url: str,
                    source_id: str = "kagoshima_pref_sale") -> list[Listing]:
        soup = BeautifulSoup(content, "html.parser")
        listings: list[Listing] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if "bukenholder" not in a["href"] and "物件明細" not in text:
                continue
            # 「売却中の物件明細」「今後売却予定の物件明細」等の案内ページは
            # 物件ではないので拾わない (2026-08-09 実地確認)
            if a["href"].rstrip("/").endswith("index.html"):
                continue
            url = urljoin(base_url, a["href"])
            if url in seen or not text:
                continue
            seen.add(url)
            # 「物件明細（旧姶良警察署（庁舎）跡地）」→ 外側の括弧だけ剥がす
            # (入れ子括弧があるため正規表現の最短一致では名前が欠ける)
            name = text.replace("物件明細", "").strip()
            if name.startswith("（") and name.endswith("）"):
                name = name[1:-1]
            name = name or text
            listings.append(Listing(
                source=source_id,
                listing_id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
                title=f"県有財産売却: {name}",
                url=url,
                price_yen=None,
                address="",   # 明細側にしか無い。空なら本体のエリア除外は通らない
                description=text,
                raw={"link_text": text},
            ))
        return listings
