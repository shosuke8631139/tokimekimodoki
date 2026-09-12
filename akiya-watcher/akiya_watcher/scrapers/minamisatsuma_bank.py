"""南さつま市 空き家バンク(市直営・地域別5ページ)アダプタ。

ページ構成:
- 加世田: e016252.html
- 笠沙:   e016253.html
- 大浦:   e016255.html
- 坊津:   e016256.html
- 金峰:   e016254.html

各ページに物件ごとの table が並び、以下の行を含む:
- 登録番号: No.xxx (詳細ページへのリンクがある場合あり)
- 所在地: 加世田内山田...
- 建物: 構造、床面積、建築年など
- 土地: 土地面積など
- 価格: ●売却：700万円 / ●賃貸：... など
- 不動産業者: 業者名、電話、所在地

落とし穴対策:
1. 家賃誤認防止: 「売却」「売買」ラベルの付いた価格のみを抽出。
   賃貸のみの物件は売買価格なし(None)とする。
2. 過去の値下げ文字による誤通知防止: 初回取得時は基準価格登録とし、
   SQLite DBの価格差分で実質的な値下げを検知する。
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..criteria import parse_area_sqm, parse_price_yen
from ..models import Listing
from .base import BaseScraper

_NO_RE = re.compile(r"([0-9]+(?:-[0-9]+)?)")
_SALE_PRICE_RE = re.compile(r"(?:売却|売買)[^0-9]{0,8}([0-9,]+(?:\.[0-9]+)?(?:億|万)?(?:円)?)")


class MinamisatsumaBankScraper(BaseScraper):
    source_id = "minamisatsuma_akiya_bank"
    full_snapshot = True
    prices_reliable = True

    DEFAULT_LIST_URLS = [
        "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-itiran/e016252.html",  # 加世田
        "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-itiran/e016253.html",  # 笠沙
        "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-itiran/e016255.html",  # 大浦
        "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-itiran/e016256.html",  # 坊津
        "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-itiran/e016254.html",  # 金峰
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        self.list_urls = config.get("list_urls") or self.DEFAULT_LIST_URLS

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        self.full_snapshot = True
        for url in self.list_urls:
            try:
                res = self.get(url)
                res.encoding = res.apparent_encoding or "utf-8"
                page = self.parse_page(res.text, url)
                if not page:
                    raise ValueError("物件テーブルがありません。掲載終了判定を保留します")
                for item in page:
                    item.source = self.source_id
                listings.extend(page)
            except Exception as e:
                self.full_snapshot = False
                print(f"[warn] 南さつま市取得失敗: {url} ({type(e).__name__}: {e})")
        if not listings:
            raise ValueError("南さつま市の全ページを取得できませんでした")
        return listings

    @classmethod
    def parse_page(cls, html: str, page_url: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        for old in soup.select("del, s, strike, [style*=line-through]"):
            old.decompose()
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else ""
        region_match = re.search(r"（([^）]+)一覧）|([加笠大坊金][^\s（]+)", page_title)
        region = region_match.group(1) or region_match.group(2) if region_match else ""

        listings: list[Listing] = []
        for table in soup.find_all("table"):
            data: dict[str, str] = {}
            detail_url = ""

            for tr in table.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                if len(cells) != 2:
                    continue
                k = unicodedata.normalize("NFKC", cells[0].get_text(strip=True))
                v = unicodedata.normalize("NFKC", cells[1].get_text(" ", strip=True))

                a_tag = cells[1].find("a", href=True)
                if a_tag and not detail_url:
                    detail_url = urljoin(page_url, a_tag["href"])

                data[k] = v

            # 登録番号がなければ物件テーブルではない
            raw_no = data.get("登録番号", "")
            no_match = _NO_RE.search(raw_no)
            if not no_match:
                continue
            number = no_match.group(1)

            # 価格の判定 (売却・売買価格のみを抽出。賃貸は誤認防止のため除外)
            price_str = data.get("価格", "")
            price_yen: int | None = None
            if "売却" in price_str or "売買" in price_str:
                sale_match = _SALE_PRICE_RE.search(price_str)
                if sale_match:
                    price_yen = parse_price_yen(sale_match.group(1))
            elif "賃貸" in price_str and not ("売却" in price_str or "売買" in price_str):
                # 賃貸のみの物件は売買価格なし
                price_yen = None
            else:
                price_yen = parse_price_yen(price_str)

            # 住所
            addr = data.get("所在地", "")
            full_address = addr if addr.startswith("鹿児島県") else f"鹿児島県南さつま市{addr}"

            # 建物・土地
            building_str = data.get("建物", "")
            land_str = data.get("土地", "")
            floor_area = parse_area_sqm(building_str)
            land_area = parse_area_sqm(land_str)

            # 業者・連絡先
            agent_str = data.get("仲介不動産業者", data.get("不動産業者", ""))

            # 詳細URL (なければ一覧のアンカー)
            listing_url = detail_url if detail_url else f"{page_url}#no-{number}"

            desc_parts = [
                f"登録番号: {number}",
                f"建物: {building_str}" if building_str else "",
                f"土地: {land_str}" if land_str else "",
                f"価格表記: {price_str}" if price_str else "",
                f"取扱業者: {agent_str}" if agent_str else "",
            ]
            description = " / ".join(p for p in desc_parts if p)

            listings.append(Listing(
                source=cls.source_id,
                listing_id=f"minamisatsuma-{number}",
                title=f"南さつま市空き家バンク No.{number}" + (f"（{region}）" if region else ""),
                url=listing_url,
                price_yen=price_yen,
                address=full_address,
                floor_area_sqm=floor_area,
                land_area_sqm=land_area,
                description=description,
                raw=data,
            ))

        return listings
