"""薩摩川内市 空き家バンク(市直営CGI)アダプタ。

経緯 (2026-08-03 実地確認):
- アットホーム系サイト(3件)とは別に、市サイトのCGI一覧に約20件の実体があった
  (都城と同じ「バンクの実体が別の場所」パターン)
  https://www.city.satsumasendai.lg.jp/cgi-bin/recruit.php/3/list
- 一覧の各物件は .entry-list-box。リンク文字列が台帳そのもの:
    「交渉中 08004/薩摩川内市樋脇町市比野1321-1/売買 100万」
    「08005/薩摩川内市鹿島町藺牟田212-2/賃貸1万円、売買50万円」
  → 管理番号・所在地・売買価格(万円建て)が一覧の文字列から読める
- 売買価格が読めた物件のみ採用 (賃貸のみは対象外 = 買えない物件は追わない)。
  そのため prices_reliable=True (価格Noneの取りこぼしを台帳に入れない)
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

_NUMBER = re.compile(r"\b(\d{5})\b")
_ADDR = re.compile(r"(薩摩川内市[^/【】\s]+)")
# 「売買 100万」「売買50万円」「売買 1,200万円」。応相談・交渉はここで弾く
_BUY_MAN = re.compile(r"売買[^0-9応交]{0,4}([0-9,]+(?:\.[0-9]+)?)\s*万")
_BUY_YEN = re.compile(r"売買[^0-9応交]{0,4}([0-9][0-9,]{4,})\s*円")
_FLAG = re.compile(r"交渉中|更新|新着|値下げ")


class SatsumasendaiCityScraper(BaseScraper):
    source_id = "satsumasendai_city"
    full_snapshot = True    # CGI一覧が全量。消えたら掲載終了(成約)扱い
    prices_reliable = True  # 売買価格が読めない物件は最初から採用しない設計

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        self.list_url = config["list_url"]
        self.max_pages = config.get("max_pages", 3)

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_pages: set[str] = set()
        url = self.list_url
        for _ in range(self.max_pages):
            if not url or url in seen_pages:
                break
            seen_pages.add(url)
            res = self.get(url)
            res.encoding = res.apparent_encoding
            items, url = self.parse_index(res.text, url)
            listings.extend(items)
        uniq: dict[str, Listing] = {}
        for ls in listings:
            uniq.setdefault(ls.listing_id, ls)
        return list(uniq.values())

    @staticmethod
    def parse_index(html: str, base_url: str,
                    ) -> tuple[list[Listing], str | None]:
        """一覧HTMLから (売買物件のリスト, 次ページURL or None) を返す。"""
        soup = BeautifulSoup(html, "html.parser")
        out: list[Listing] = []
        for box in soup.select(".entry-list-box"):
            a = box.find("a", href=True)
            if a is None:
                continue
            text = unicodedata.normalize(
                "NFKC", box.get_text(" ", strip=True))
            m = _BUY_MAN.search(text)
            if m:
                price_yen = int(float(m.group(1).replace(",", "")) * 10_000)
            else:
                m = _BUY_YEN.search(text)
                if m is None:
                    continue    # 賃貸のみ・価格なし = 対象外
                price_yen = int(m.group(1).replace(",", ""))
            mnum = _NUMBER.search(text)
            madr = _ADDR.search(text)
            detail_url = urljoin(base_url, a["href"])
            # 管理番号が読めない場合は詳細URL末尾のIDで代用
            number = mnum.group(1) if mnum else \
                (re.search(r"detail/(\d+)", detail_url) or ["", "?"])[1]
            place = madr.group(1).replace("薩摩川内市", "") if madr else ""
            flags = " ".join(dict.fromkeys(_FLAG.findall(text)))
            title = f"薩摩川内市空き家バンク No.{number}"
            if place:
                title += f"（{place[:12]}）"
            title += "【売買】" + (f" {flags}" if flags else "")
            out.append(Listing(
                source="satsumasendai_city",
                listing_id=f"sendai-city-{number}",
                title=title[:120],
                url=detail_url,
                price_yen=price_yen,
                address=f"鹿児島県{madr.group(1)}" if madr else "鹿児島県薩摩川内市",
                description=text[:800],
                raw={"number": number},
            ))
        # ページ送り: 同じCGIの list を指す「次」リンクがあれば辿る
        next_url = None
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            if "次" in label and "recruit.php" in a["href"]:
                next_url = urljoin(base_url, a["href"])
                break
        return out, next_url
