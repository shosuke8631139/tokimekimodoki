"""KSI官公庁オークション (公売・公有財産売却) の不動産一覧アダプタ。

2026-08-09 偵察結果 (Actions run 31315520891 / 31315669435) に基づく:
  - robots.txt は「Allow: /search/real-estate/$」でこの一覧URLだけを明示許可。
    クエリ付きの2ページ目以降と /api/ は不許可のため、1ページ目のみ読む。
  - Pythonの urllib.robotparser は末尾 $ を解釈できず、この明示許可を
    誤って「不許可」と判定する。そのため本アダプタは robots.txt の
    Allow行が現存することを自分で確認してから取得する (行が消えたら止まる)。
  - ページはNext.js製だがサーバ側レンダリングで、物件カードのHTMLに
    タイトル・物件価格・所在地・カテゴリ・間取りが全部入っている。
  - 1物件につき /items/<数字>/ へのリンクが複数あるためIDで一意化する。
  - タイトルは「鹿児島県薩摩川内市青山町　宅地１区画ほか【…】」のように
    県名から始まることが多い。所在地欄には県名が無いことがあるため、
    住所は「所在地欄 (タイトル)」を合わせてエリア判定が通るようにする。
  - 入札ラウンド制のため、ラウンド間は全物件が「入札終了」表示になる。
    終了物件は台帳に入れず、新ラウンドの公開を新着として拾うのが役目。

公売は税金滞納の差押財産。入札期日があるため、値下げ待ちではなく
「新着(新ラウンド)を見逃さない」ことが主目的。入札終了で一覧から
消えるのは自然な流れなので full_snapshot=False (掲載終了通知を出さない)。
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

LIST_URL = "https://kankocho.jp/search/real-estate/"
ALLOW_LINE = "Allow: /search/real-estate/$"

# 物件カードに出る状態ラベル (2026-08-09 実地確認: 入札開始待ちも存在)
STATUS_LABELS = ("入札終了", "受付終了", "入札開始待ち", "入札中", "受付中",
                 "入札予定", "公開中")
CLOSED_LABELS = ("入札終了", "受付終了")


class KsiAuctionScraper(BaseScraper):
    source_id = "ksi_auction"
    # 1ページ目しか見ない+入札終了で消えるため「消えた=売れた」とは扱わない
    full_snapshot = False

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config["id"]
        self.list_url = config.get("list_url", LIST_URL)
        # 入札が終わった物件も返すか (本番: False。接続テストでは True で
        # ラウンド間でもカード解析を検証できるようにする)
        self.include_closed = config.get("include_closed", False)
        self._allow_confirmed: bool | None = None

    # ------------------------------------------------------------ robots
    def _allowed_by_robots(self, url: str) -> bool:
        """一覧URLだけは robots.txt の明示Allow行を直接確認する。

        標準の robotparser は「Allow: /search/real-estate/$」の $ を解釈
        できず不許可と誤判定するため、サイトの意図(この一覧のみ許可)を
        原文で確認する。Allow行が消えたら取得しない。
        """
        if urlparse(url).path.rstrip("/") != "/search/real-estate":
            return super()._allowed_by_robots(url)
        if self._allow_confirmed is None:
            try:
                res = self.session.get("https://kankocho.jp/robots.txt",
                                       timeout=30)
                self._allow_confirmed = (res.status_code == 200
                                         and ALLOW_LINE in res.text)
            except Exception:
                self._allow_confirmed = False
        return self._allow_confirmed

    # ------------------------------------------------------------ 取得
    def fetch_listings(self) -> list[Listing]:
        res = self.get(self.list_url)
        return self.parse_list(res.text, self.list_url, self.source_id,
                               include_closed=self.include_closed)

    # ------------------------------------------------------------ 解析
    @classmethod
    def parse_list(cls, html: str, base_url: str, source_id: str = "ksi_auction",
                   include_closed: bool = False) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        listings: list[Listing] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            m = re.match(r"^/items/(\d+)/?$", a["href"])
            if not m:
                continue
            item_id = m.group(1)
            if item_id in seen:
                continue
            # 同一物件へのリンクが複数ある。状態ラベルだけのリンクは飛ばし、
            # タイトルを持つリンクを本命として使う
            text = a.get_text(" ", strip=True)
            if not text or text in STATUS_LABELS:
                continue
            seen.add(item_id)
            card = cls._card_of(a)
            listing = cls._parse_card(item_id, text, a["href"], card,
                                      base_url, source_id, include_closed)
            if listing is not None:
                listings.append(listing)
        return listings

    @staticmethod
    def _card_of(anchor):
        """タイトルリンクから物件カード全体 (価格・所在地を含む祖先) を探す。"""
        node = anchor
        for _ in range(8):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if "物件価格" in text and "所在地" in text:
                return node
        return anchor.parent or anchor

    @classmethod
    def _parse_card(cls, item_id: str, title: str, href: str, card,
                    base_url: str, source_id: str,
                    include_closed: bool) -> Listing | None:
        tokens = [t.strip() for t in card.get_text("|", strip=True).split("|")
                  if t.strip()]
        text = " ".join(tokens)

        status = next((s for s in STATUS_LABELS if s in text), "")
        if status in CLOSED_LABELS and not include_closed:
            return None

        price = cls._field_number(tokens, "物件価格")
        address = cls._field_value(tokens, "所在地")
        category = cls._field_value(tokens, "カテゴリ")
        layout = cls._field_value(tokens, "間取り")
        # 所在地に県名が無い物件があるためタイトル(県名始まりが多い)を併記し、
        # target_areas の市町村名マッチが通るようにする
        if address and title and title not in address:
            address = f"{address} ({title})"
        elif not address:
            address = title

        description = " ".join(
            p for p in [status, f"カテゴリ:{category}" if category else "",
                        text[:400]] if p)
        return Listing(
            source=source_id,
            listing_id=item_id,
            title=title,
            url=urljoin(base_url, href),
            price_yen=price,
            address=address,
            layout=layout,
            description=description,
            raw={"status": status, "category": category},
        )

    @staticmethod
    def _field_value(tokens: list[str], label: str) -> str:
        """「ラベル | 値」形式のトークン列から値を取り出す。"""
        for i, t in enumerate(tokens):
            if t == label and i + 1 < len(tokens):
                return tokens[i + 1]
        return ""

    @staticmethod
    def _field_number(tokens: list[str], label: str) -> int | None:
        """「物件価格 | 195,000 | 円」のような数値欄を読む。"""
        for i, t in enumerate(tokens):
            if t == label and i + 1 < len(tokens):
                digits = re.sub(r"[^\d]", "", tokens[i + 1])
                if digits:
                    return int(digits)
        return None
