"""湧水町 空家バンクアダプタ。

ページ構造 (2026-08 GitHub Actions で実地確認):
    <td>
      <p><strong>No.250　売買２００万円</strong>［木場］</p>
      <p><a href="/soshiki/34/11308.html"><img alt="外観" src="..."/></a></p>
    </td>
  が表のセルとして並ぶ。表記ゆれ:
    - 全角数字 (２００万円)・カンマ (1,000万円)・「応相談」
    - No と価格が別々の <strong> に分かれる物件 (No.127 など)
    - 枝番 (No.169-3)
    - 賃貸のみの物件も混ざる (賃貸4.5万円/月) → 売買のみ収集
  地区名は ［木場］ のように全角角括弧で入る。

robots.txt は町サイト共通 (取得可)。物件IDは No 番号から作る。
空地バンク(789.html)は土地のみのため対象にしない。
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..criteria import parse_price_yen
from ..models import Listing
from .base import BaseScraper

_NO = re.compile(r"No\.?\s*([0-9]+(?:-[0-9]+)?)", re.IGNORECASE)
_PLACE = re.compile(r"[［\[]([^］\]]+)[］\]]")


class YusuiBankScraper(BaseScraper):
    source_id = "yusui_bank"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        self.list_url = config["list_url"]

    def fetch_listings(self) -> list[Listing]:
        res = self.get(self.list_url)
        res.encoding = res.apparent_encoding
        return self.parse(res.text)

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        listings: list[Listing] = []
        seen: set[str] = set()
        for td in soup.find_all("td"):
            strongs = td.find_all("strong")
            if not strongs:
                continue
            # No と価格が別 strong の物件があるため、td 内の strong を連結して読む
            head = unicodedata.normalize(
                "NFKC", " ".join(s.get_text(" ", strip=True) for s in strongs))
            head = " ".join(head.split())
            m = _NO.search(head)
            if m is None:
                continue
            number = m.group(1)
            if number in seen:      # ナビゲーション等の重複防止
                continue
            if "売買" not in head:  # 賃貸のみの物件は収集しない
                continue
            seen.add(number)

            # 売買と賃貸が併記される物件があるため、売買の後ろだけを読む
            # (賃貸額を売買価格と誤読しない。実地確認: No.92)
            price_part = head.split("売買", 1)[1].split("賃貸")[0]
            price_yen = parse_price_yen(price_part)  # 「応相談」は None になる

            td_text = unicodedata.normalize("NFKC", td.get_text(" ", strip=True))
            pm = _PLACE.search(td_text)
            place = pm.group(1).strip() if pm else ""

            a = td.find("a", href=True)
            url = urljoin(self.list_url, a["href"]) if a else self.list_url

            listings.append(Listing(
                source=self.source_id,
                listing_id=f"yusui-{number}",
                title=f"湧水町空家バンク No.{number}（{place or '場所不明'}）【売買】",
                url=url,
                price_yen=price_yen,
                address=f"鹿児島県姶良郡湧水町{place}",
                description=head,
                raw={"head": head, "place": place},
            ))
        return listings
