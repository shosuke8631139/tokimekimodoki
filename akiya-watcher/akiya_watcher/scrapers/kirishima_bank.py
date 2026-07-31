"""霧島市 空き家バンク(地区別一覧)アダプタ。

ページ構造 (2026-07 GitHub Actions で実地確認):
    <table class="datatable"> の th/td 行に
      登録No / 更新日 / 所在地 / 種類(売買物件・賃貸物件) / 価格(または賃料) /
      築年月 / その他
    が並び、表の直後の <ul> に「空き家バンク登録カード(No.xxx)(PDF)」への
    リンクが付く。地区別に7ページある(list_urls で全ページを巡回)。

売買物件のみ収集する(賃貸掲載は物件探しの対象外)。
物件IDは登録Noから作る。
"""
from __future__ import annotations

import re
import time

import requests
from bs4 import BeautifulSoup

from ..criteria import parse_price_yen
from ..models import Listing
from .base import BaseScraper

_CARD_PAT = re.compile(r"登録カード")


class KirishimaBankScraper(BaseScraper):
    source_id = "kirishima_bank"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        self.list_urls: list[str] = config.get("list_urls") or [config["list_url"]]
        # 市サーバは巡回間隔(10秒)の間に keep-alive を切ることがあり、
        # 死んだ接続の再利用で RemoteDisconnected になる。毎回張り直す。
        self.session.headers["Connection"] = "close"

    def _get_with_retry(self, url: str, attempts: int = 3):
        for i in range(attempts):
            try:
                return self.get(url)
            except requests.exceptions.ConnectionError:
                if i == attempts - 1:
                    raise
                time.sleep(3)

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        for url in self.list_urls:
            res = self._get_with_retry(url)
            res.encoding = res.apparent_encoding
            listings.extend(self.parse(res.text, url))
        return listings

    def parse(self, html: str, page_url: str) -> list[Listing]:
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")
        listings: list[Listing] = []
        for table in soup.select("table.datatable"):
            fields: dict[str, str] = {}
            for tr in table.find_all("tr"):
                th, td = tr.find("th"), tr.find("td")
                if th is None or td is None:
                    continue
                key = " ".join(th.get_text(" ", strip=True).split())
                value = " ".join(td.get_text(" ", strip=True).split())
                if key:
                    fields.setdefault(key, value)

            number = fields.get("登録No", "").strip()
            kind = fields.get("種類", "")
            if not number or "売買" not in kind:
                continue

            # 価格の欄名は「価格」想定だが、揺れに備えて「万円」を含む値も探す
            price_text = fields.get("価格", "")
            if not price_text:
                for key, value in fields.items():
                    if "万円" in value and key not in ("賃料", "その他", "所在地"):
                        price_text = value
                        break
            price_yen = parse_price_yen(price_text)

            # 表の直後にある登録カードPDFへのリンク
            card = table.find_next("a", string=_CARD_PAT)
            card_url = urljoin(page_url, card["href"]) if card and card.get("href") else page_url

            address = fields.get("所在地", "")
            listings.append(Listing(
                source=self.source_id,
                listing_id=f"kirishima-{number}",
                title=f"霧島市空き家バンク No.{number}（{address or '所在地不明'}）【売買】",
                url=card_url,
                price_yen=price_yen,
                address=f"鹿児島県霧島市{address}",
                description=" / ".join(v for v in [fields.get("その他", ""),
                                                   fields.get("築年月", "")] if v),
                raw=fields,
            ))
        return listings
