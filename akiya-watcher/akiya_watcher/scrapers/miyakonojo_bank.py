"""都城市 空き家バンク(移住サイト「住めば住むほど都城」)アダプタ。

経緯 (2026-08 実地確認):
- 都城のアットホーム系サイト(miyakonojo-c45202)は空。市の空き家バンクは
  移住特設サイト sumeba-sumuhodo-miyakonojo.jp に移行していた
- robots.txt は wp-admin のみ Disallow (一覧・詳細の取得は許可)
- 一覧 /residence/ の物件リンクはURL自体が台帳になっている親切設計:
    /residence/【管理番号421】売買（蓑原町）/
    /residence/【管理番号418】売買-土地（下長飯町）/
  → 管理番号・取引種別・地区がURLから読める。売買のみ採用(土地・賃貸は除外)
- 価格はURLに無いため、詳細ページを開いてラベル付き価格を読む
  (礼儀: 基底クラスの10秒間隔に従い、詳細取得は上限8件/巡回)

一覧が1ページに収まる想定で実装(ページ送りは未確認のため
full_snapshot=False とし、見えない物件を掲載終了と誤記録しない)。
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote

from bs4 import BeautifulSoup

from ..models import Listing
from .base import BaseScraper

# NFKC正規化で全角括弧（）は半角()になるため両対応で読む
_SLUG = re.compile(r"管理番号(\d+)】([^（）()/]*)[（(]([^（）()]+)[）)]")
# 実表記 (2026-08 実地確認): 「価格 5,800,000円」の円建て。万円建てにも両対応
_PRICE_MAN = re.compile(
    r"(?:価格|販売価格|売買価格|希望価格|売却価格)[^0-9応交]{0,8}"
    r"([0-9,]+(?:\.[0-9]+)?)\s*万円")
_PRICE_YEN = re.compile(
    r"(?:価格|販売価格|売買価格|希望価格|売却価格)[^0-9応交]{0,8}"
    r"([0-9][0-9,]{4,})\s*円")
_INFO_HINT = re.compile(r"間取|築|構造|価格|残置|接道|駐車|土地|建物|万円|㎡|平米"
                        r"|現状|渡し|相続|スーパー|コンビニ|学校|病院|役場|駅|バス")


class MiyakonojoBankScraper(BaseScraper):
    source_id = "miyakonojo_sumeba"
    full_snapshot = False     # ページ送り未確認のため掲載終了判定はしない
    # 2026-08-03 ユーザー要望「300万超が混ざる」対応: 価格が読めなかった物件を
    # 「価格不明(指値候補)」として台帳に通すと、実際は高額の物件が紛れ込む。
    # 価格Noneは応相談カットで落とす (=売買価格が読めた物件だけ採用)
    prices_reliable = True
    MAX_DETAILS = 8           # 1巡回で詳細ページを開く上限 (礼儀)

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        self.list_url = config["list_url"]

    def fetch_listings(self) -> list[Listing]:
        res = self.get(self.list_url)
        res.encoding = "utf-8"
        items = self.parse_index(res.text)
        listings: list[Listing] = []
        for i, (number, place, url) in enumerate(items):
            price_yen = None
            desc = ""
            if i < self.MAX_DETAILS:
                try:
                    d = self.get(url)
                    d.encoding = "utf-8"
                    price_yen, desc = self.parse_detail(d.text)
                except Exception as exc:  # noqa: BLE001
                    print(f"[warn] {self.source_id}: 詳細取得失敗 {url} ({exc})")
            listings.append(Listing(
                source=self.source_id,
                listing_id=f"miyakonojo-{number}",
                title=f"都城市空き家バンク No.{number}（{place}）【売買】",
                url=url,
                price_yen=price_yen,
                address=f"宮崎県都城市{place}",
                description=desc,
                raw={"number": number, "place": place},
            ))
        return listings

    @staticmethod
    def parse_index(html: str) -> list[tuple[str, str, str]]:
        """一覧HTMLから (管理番号, 地区, 詳細URL) を返す。売買のみ。"""
        soup = BeautifulSoup(html, "html.parser")
        out: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/residence/" not in href:
                continue
            decoded = unicodedata.normalize("NFKC", unquote(href))
            m = _SLUG.search(decoded)
            if m is None:
                continue
            number, kind, place = m.group(1), m.group(2), m.group(3)
            if number in seen:
                continue
            if "売買" not in kind or "土地" in kind or "賃貸" in kind:
                continue        # 売買の建物のみ (土地のみ・賃貸は対象外)
            seen.add(number)
            out.append((number, place.strip(), href))
        return out

    @staticmethod
    def parse_detail(html: str) -> tuple[int | None, str]:
        """詳細HTMLから (価格円, 説明文) を返す。価格が読めなければ None。"""
        soup = BeautifulSoup(html, "html.parser")
        # 検索フォーム(価格の選択肢に「万円」が並ぶ)を除外してから本文を読む
        for form in soup.find_all("form"):
            form.decompose()
        text = unicodedata.normalize("NFKC", soup.get_text(" ", strip=True))
        price_yen = None
        m = _PRICE_MAN.search(text)
        if m:
            price_yen = int(float(m.group(1).replace(",", "")) * 10_000)
        else:
            m = _PRICE_YEN.search(text)
            if m:
                price_yen = int(m.group(1).replace(",", ""))
        # 物件情報らしい文だけを説明文として拾う (仕入れ点・周辺抽出の材料)
        parts = [seg.strip() for seg in re.split(r"[。\n]", text)
                 if _INFO_HINT.search(seg)]
        desc = "。".join(parts)[:400]
        return price_yen, desc
