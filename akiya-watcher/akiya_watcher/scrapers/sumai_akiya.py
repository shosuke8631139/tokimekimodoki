"""Sumai空き家 (akiya.sumai.biz) アダプタ。

全国の自治体空き家バンクの物件を集約しているサイト。物件タイトルに
情報が詰まっているのが特徴で、価格変更まで明示される:

  (価格変更)空き家バンク【売買】300万円→100万円 鹿児島県霧島市隼人町小浜
  海水浴場近い・桜島を望む バルコニー・駐車場付き5SLDK平屋 水洗トイレ

そのためHTML構造(CSSセレクタ)に依存せず、ページ内の全リンクから
「物件タイトルの形をした文字列」を拾う方式にする。サイト側のデザイン変更に
強く、一覧ページ・地域ページのどちらでも動く。

「→」表記があれば変更前価格を advertised_previous_price_yen に入れる。
これにより初回取得時から値下げ物件として扱われる(履歴不要)。

有効化前に robots.txt と利用規約を必ず確認すること(BaseScraper が
robots.txt を自動チェックするが、規約の確認は人間の仕事)。
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..criteria import parse_price_yen
from ..models import Listing
from .base import BaseScraper

# "300万円→100万円" / "300万円 → 100万円"
ARROW_PAT = re.compile(
    r"([0-9,]+(?:\.[0-9]+)?\s*(?:億[0-9,]*)?万円)\s*(?:→|⇒)\s*"
    r"([0-9,]+(?:\.[0-9]+)?\s*(?:億[0-9,]*)?万円)")
PRICE_PAT = re.compile(r"[0-9,]+(?:\.[0-9]+)?\s*(?:億[0-9,]*)?万円")
# "鹿児島県霧島市隼人町小浜" のような住所らしき並び
ADDRESS_PAT = re.compile(r"([一-龥]{2,4}[都道府県][^\s　【】()()]+)")
RENTAL_PAT = re.compile(r"【賃貸】|賃貸物件")


def parse_listing_title(title: str) -> dict | None:
    """物件タイトル文字列を解析する。物件らしくなければ None。"""
    t = " ".join(title.split())
    if not t or RENTAL_PAT.search(t):
        return None
    # 「空き家バンク」または売買表記+価格があるものだけを物件とみなす
    if not PRICE_PAT.search(t):
        return None
    if "空き家バンク" not in t and "【売買】" not in t and "売買" not in t:
        return None

    prev_price = None
    m = ARROW_PAT.search(t)
    if m:
        prev_price = parse_price_yen(m.group(1))
        price = parse_price_yen(m.group(2))
    else:
        price = parse_price_yen(PRICE_PAT.search(t).group(0))

    am = ADDRESS_PAT.search(t)
    address = am.group(1) if am else ""
    return {
        "title": t,
        "price_yen": price,
        "advertised_previous_price_yen": prev_price,
        "address": address,
    }


class SumaiAkiyaScraper(BaseScraper):
    source_id = "sumai_akiya"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", "sumai_akiya")
        self.list_urls: list[str] = config.get("list_urls", [])

    def _canonical(self, url: str) -> str:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

    def fetch_listings(self) -> list[Listing]:
        found: dict[str, Listing] = {}
        for page_url in self.list_urls:
            res = self.get(page_url)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                parsed = parse_listing_title(a.get_text(" ", strip=True))
                if parsed is None:
                    continue
                url = urljoin(page_url, a["href"])
                canon = self._canonical(url)
                if canon in found:
                    continue
                found[canon] = Listing(
                    source=self.source_id,
                    listing_id=hashlib.sha256(canon.encode()).hexdigest()[:16],
                    title=parsed["title"][:200],
                    url=url,
                    price_yen=parsed["price_yen"],
                    address=parsed["address"],
                    # タイトル自体に間取り・駐車場・トイレ等の語が含まれるので
                    # description にも入れてスコアラーのキーワード判定に乗せる
                    description=parsed["title"],
                    advertised_previous_price_yen=parsed["advertised_previous_price_yen"],
                    raw={"canonical_url": canon},
                )
        return list(found.values())
