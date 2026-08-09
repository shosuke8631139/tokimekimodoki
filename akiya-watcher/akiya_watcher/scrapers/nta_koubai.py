"""国税庁 公売情報 (差押不動産のインターネット公売・期間入札) アダプタ。

2026-08-09 偵察結果 (Actions run 31315520891 / 31315669435) に基づく:
  - robots.txt なし (404) = クロール制限なし。素直なPHP+GETの検索システム。
  - 一覧は hp0241.php にGETパラメータ (財産種別チェックボックス等) を付けて
    取得する。ページ送りは pageid=1,2,... (現在全国75件・30件/ページ)。
  - 各物件は hp0201.php への詳細リンクとして並ぶ。一覧行に「見積価額」の
    ラベルは無く、価格・所在地は行テキストから推定で読む。読めない場合は
    None/空で台帳に残す (prices_reliable=False なので応相談カットされない)。
  - 全国の物件が流れるが、リサーチ範囲外は本体の target_areas フィルタが
    落とす。ここでは落とさない (設計思想: 条件で落とさない)。

公売は入札期間があるため「新着を見逃さない」ことが主目的。期間終了で
一覧から消えるのは自然な流れなので full_snapshot=False。
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

BASE_URL = "https://www.koubai.nta.go.jp/auctionx/public/hp0241.php"
# 財産の種類: 100=土地 110=建物 120=土地付建物 130=区分所有建物
#             190=農地 999=その他不動産 (偵察で確認したチェックボックス)
SEARCH_PARAMS = ("?addr_id=0&addr_area=0&addr_wide=0&addr_or_line=0&addr_name=0"
                 "&zaisan_bunrui_chk%5B100%5D=1&zaisan_bunrui_chk%5B110%5D=1"
                 "&zaisan_bunrui_chk%5B120%5D=1&zaisan_bunrui_chk%5B130%5D=1"
                 "&zaisan_bunrui_chk%5B190%5D=1&zaisan_bunrui_chk%5B999%5D=1")

PREF_PAT = re.compile(
    r"(?:北海道|(?:京都|大阪)府|東京都|[一-龥]{2,3}県)[一-龥0-9０-９ー―\-]*")
PRICE_PAT = re.compile(r"([0-9,，]{4,})\s*円")


class NtaKoubaiScraper(BaseScraper):
    source_id = "nta_koubai"
    full_snapshot = False     # 入札期間の終了 = 掲載終了は自然な流れ
    prices_reliable = False   # 一覧行からの推定読みのため None を落とさない

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config["id"]
        self.pages = int(config.get("pages", 3))  # 30件/頁 × 3頁 = 90件分

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        seen: set[str] = set()
        for page in range(self.pages):
            url = BASE_URL + SEARCH_PARAMS + (f"&pageid={page}" if page else "")
            res = self.get(url)
            page_items = self.parse_list(res.text, url, self.source_id)
            new_items = [ls for ls in page_items if ls.uid not in seen]
            seen.update(ls.uid for ls in new_items)
            listings.extend(new_items)
            # 末尾ページ (物件が減った/無い) 以降は読まない
            if not new_items:
                break
        return listings

    # ------------------------------------------------------------ 解析
    @classmethod
    def parse_list(cls, html: str, page_url: str,
                   source_id: str = "nta_koubai") -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        listings: list[Listing] = []
        seen_href: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "hp0201.php" not in href:
                continue
            if href in seen_href:
                continue
            seen_href.add(href)
            title = a.get_text(" ", strip=True)
            row = cls._row_of(a)
            row_text = row.get_text(" ", strip=True) if row is not None else ""
            if not title:
                title = row_text[:60] or "(無題)"
            price = cls._parse_price(row_text)
            address = cls._parse_address(f"{title} {row_text}")
            listings.append(Listing(
                source=source_id,
                listing_id=cls._listing_id(href),
                title=title,
                url=urljoin(page_url, href),
                price_yen=price,
                address=address,
                description=row_text[:300],
                raw={"href": href},
            ))
        return listings

    @staticmethod
    def _row_of(anchor):
        """リンクの属する物件行 (テキストが肥大しない範囲の祖先) を探す。"""
        node = anchor
        best = anchor
        for _ in range(4):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if len(text) > 600:   # ページ全体まで遡りすぎたら手前で止める
                break
            best = node
        return best

    @staticmethod
    def _parse_price(text: str) -> int | None:
        m = PRICE_PAT.search(text.replace("，", ","))
        if m:
            return int(m.group(1).replace(",", ""))
        return None

    @staticmethod
    def _parse_address(text: str) -> str:
        m = PREF_PAT.search(text)
        return m.group(0) if m else ""

    @staticmethod
    def _listing_id(href: str) -> str:
        """詳細URLから安定IDを作る。os=<番号> があればそれを使う。"""
        qs = parse_qs(urlparse(href).query)
        if qs.get("os"):
            return f"os{qs['os'][0]}"
        return hashlib.sha256(href.encode("utf-8")).hexdigest()[:16]
