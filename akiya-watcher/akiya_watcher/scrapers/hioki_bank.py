"""日置市 空き家バンク(市直営・地域別ページ)アダプタ。

経緯 (2026-08-03 実地確認):
- 日置市は市サイト直営のバンクを地域別4ページで運営 (東市来/伊集院/日吉/吹上)。
  各ページに表形式で20〜35件。「値下げ！」「蔵付き」「納屋」の文言が
  セルにそのまま載る (仕入れ点エンジンの得意分野)
- 表の行構成: 物件番号(詳細リンク) | 建物情報など | お問い合わせ先。
  詳細URLは bukkenNNN.html / bukkennNNN.html の表記ゆれあり
- 価格は円建て (例: 3,000,000円)。売却価格が読めた物件のみ採用
  (賃貸のみは対象外)。そのため prices_reliable=True
- ユーザー指名物件は詳細ページも直接読む。一覧と詳細の更新がずれている時は
  安い方を現在価格として採用し、同じ物件番号へ統合して二重登録しない
- 市の制度メモ: 「空き家の家財道具処分を支援」補助あり。
  入居者(テナント)自身が申請できるDIY改修補助も設計書の補助金マップ参照
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

# ラベル付き売却価格を最優先で読む
_SALE_PRICE = re.compile(
    r"(?:売却希望価格|売却価格|販売価格|価格)[^0-9]{0,8}([0-9][0-9,]{4,})\s*円")
_ANY_YEN = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+)\s*円")
_REGION = re.compile(r"([一-龥]+)地域")
# 地域名 → 住所に使う町名
_REGION_TOWN = {"東市来": "東市来町", "伊集院": "伊集院町",
                "日吉": "日吉町", "吹上": "吹上町"}
# 売却価格とみなす下限。これ未満の円額は賃料(月額)とみなす
_MIN_SALE_YEN = 200_000
_DETAIL_PRICE_BLOCK = re.compile(
    r"希望価格\s*((?:[0-9][0-9,]{4,}\s*円\s*){1,3})")


class HiokiBankScraper(BaseScraper):
    source_id = "hioki_akiya_bank"
    full_snapshot = True    # 地域別4ページで全量。消えたら掲載終了扱い
    prices_reliable = True  # 売却価格が読めない物件は採用しない設計

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        urls = config.get("list_urls") or [config["list_url"]]
        self.list_urls = urls
        self.detail_watches = config.get("detail_watches", [])

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        for url in self.list_urls:
            res = self.get(url)
            res.encoding = res.apparent_encoding
            listings.extend(self.parse_page(res.text, url))
        uniq: dict[str, Listing] = {}
        for ls in listings:
            uniq.setdefault(ls.listing_id, ls)
        for watch in self.detail_watches:
            number = str(watch.get("number", ""))
            listing = uniq.get(f"hioki-{number}")
            url = watch.get("url", "")
            if listing is None or not url:
                continue
            listing.raw["detail_watch_url"] = url
            note = watch.get("note", "")
            if note and f"追跡理由: {note}" not in listing.description:
                listing.description = f"{listing.description} / 追跡理由: {note}"[:1500]
            try:
                res = self.get(url)
                res.encoding = res.apparent_encoding
                current, previous = self.parse_detail_price(res.text)
                self.merge_detail_price(listing, current, previous)
            except Exception as exc:
                print(f"[warn] 日置市No.{number} 詳細取得失敗 "
                      f"({type(exc).__name__}: {exc})")
        return list(uniq.values())

    @staticmethod
    def parse_detail_price(html: str) -> tuple[int | None, int | None]:
        """詳細ページの「希望価格」欄から現在価格と旧価格を読む。"""
        soup = BeautifulSoup(html, "html.parser")
        text = unicodedata.normalize("NFKC", soup.get_text(" ", strip=True))
        match = _DETAIL_PRICE_BLOCK.search(text)
        if match is None:
            return None, None
        prices = [int(value.replace(",", ""))
                  for value in _ANY_YEN.findall(match.group(1))]
        if not prices:
            return None, None
        current = min(prices)
        previous = max(prices) if max(prices) > current else None
        return current, previous

    @staticmethod
    def merge_detail_price(listing: Listing, current: int | None,
                           previous: int | None) -> None:
        """一覧と詳細の更新差を吸収し、値下げ履歴を壊さず同じ物件へ統合する。"""
        if current is None:
            return
        list_price = listing.price_yen
        listing.price_yen = min(
            price for price in (list_price, current) if price is not None)
        existing_previous = listing.advertised_previous_price_yen
        if existing_previous is None or existing_previous <= listing.price_yen:
            if previous is not None and previous > listing.price_yen:
                listing.advertised_previous_price_yen = previous
        listing.raw["detail_watch_price_yen"] = current

    @staticmethod
    def parse_page(html: str, base_url: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        title_text = soup.title.get_text(strip=True) if soup.title else ""
        m = _REGION.search(title_text)
        region = _REGION_TOWN.get(m.group(1), m.group(1)) if m else ""

        out: list[Listing] = []
        for tr in soup.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            num_cell, info_cell = cells[0], cells[1]
            number = num_cell.get_text(strip=True)
            if not re.fullmatch(r"\d{1,4}", number):
                continue    # 見出し行(物件番号)や区切りは飛ばす
            info = unicodedata.normalize(
                "NFKC", info_cell.get_text(" ", strip=True))

            # 売却価格の読み方 (売却規模=20万円以上の円額だけを対象にする):
            #   値下げ行は「旧価格 → 新価格」が並ぶため小さい方が現在価格。
            #   それ以外はラベル付き(売却希望価格:)を優先する。
            #   賃料(「賃貸希望価格:月額30,000円」等)は規模で弾く。
            price_yen = None
            prev_yen = None
            m = _SALE_PRICE.search(info)
            label_yen = int(m.group(1).replace(",", "")) if m else None
            if label_yen is not None and label_yen < _MIN_SALE_YEN:
                label_yen = None
            sale_prices = [int(p.replace(",", "")) for p in _ANY_YEN.findall(info)
                           if int(p.replace(",", "")) >= _MIN_SALE_YEN]
            if "値下げ" in info and len(sale_prices) == 2:
                price_yen = min(sale_prices)
                if max(sale_prices) > price_yen:
                    prev_yen = max(sale_prices)
            elif label_yen is not None:
                price_yen = label_yen
            elif sale_prices:
                price_yen = min(sale_prices)
            if price_yen is None:
                continue    # 賃貸のみ・価格未記載 = 対象外

            a = num_cell.find("a", href=True) or tr.find("a", href=True)
            url = urljoin(base_url, a["href"]) if a else base_url
            out.append(Listing(
                source="hioki_akiya_bank",
                listing_id=f"hioki-{number}",
                title=f"日置市空き家バンク No.{number}"
                      f"（{region or '日置市'}）【売買】"[:120],
                url=url,
                price_yen=price_yen,
                address=f"鹿児島県日置市{region}",
                description=info[:800],
                advertised_previous_price_yen=prev_yen,
                raw={"number": number, "region": region},
            ))
        return out
