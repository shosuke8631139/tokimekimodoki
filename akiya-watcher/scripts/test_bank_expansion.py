"""巡回先拡張の偵察: 鹿屋市・都城市(アットホーム共通システム)+霧島市(市独自)。

1. 鹿屋・都城: 既存の generic_html 設定(鹿児島市と同じセレクタ)がそのまま
   使えるかを、本番と同じ GenericHtmlScraper で確認する。
2. 霧島市: 地区別一覧ページの構造をダンプして、アダプタが書けるか調べる。
読み取り専用テスト。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.generic_html import GenericHtmlScraper  # noqa: E402

ATHOME_FIELDS = {
    "title":       {"selector": ".property-name a", "attr": "text"},
    "url":         {"selector": ".property-name a", "attr": "href"},
    "price":       {"selector": "dl.bukken-info dd.price-strong", "attr": "text"},
    "layout":      {"selector": "dl.bukken-info dd:nth-of-type(2)", "attr": "text"},
    "land_area":   {"selector": "dl.bukken-info dd:nth-of-type(3)", "attr": "text"},
    "address":     {"selector": "dl.bukken-info dd:nth-of-type(4)", "attr": "text"},
    "description": {"selector": "dl.bukken-info", "attr": "text"},
}

ATHOME_CANDIDATES = [
    ("kanoya_akiya_bank", "https://kanoya-c46203.akiya-athome.jp/"),
    ("miyakonojo_akiya_bank", "https://miyakonojo-c45202.akiya-athome.jp/"),
]

KIRISHIMA_KOKUBU = "https://www.city-kirishima.jp/kyodo/shise/ijuteju/akiya/akiyabankkokubu.html"


def test_athome(source_id: str, url: str) -> None:
    print("=" * 78)
    print(f"### {source_id} (アットホーム共通システム想定)")
    scraper = GenericHtmlScraper({
        "id": source_id,
        "list_url": url,
        "item_selector": "ul.property-simple > li",
        "must_include": "売",
        "fields": ATHOME_FIELDS,
    })
    try:
        listings = scraper.fetch_listings()
    except Exception as exc:  # noqa: BLE001
        print(f"!! 取得失敗: {exc}")
        return
    print(f"読み取り: {len(listings)}件 (売買のみ)")
    for l in listings[:5]:
        price = f"{l.price_yen:,}円" if l.price_yen is not None else "価格不明"
        print(f"  {price} {l.address} | {l.title[:40]}")
        print(f"      {l.url}")


def recon_kirishima() -> None:
    print("=" * 78)
    print("### 霧島市 空き家バンク一覧(国分地区) 構造偵察")
    res = requests.get(KIRISHIMA_KOKUBU, timeout=30,
                       headers={"User-Agent": "akiya-watcher/0.1 (structure test)"})
    res.encoding = res.apparent_encoding
    print(f"status={res.status_code} bytes={len(res.text)}")
    soup = BeautifulSoup(res.text, "html.parser")
    # 物件番号・価格らしき文字を含む要素の祖先タグを観察
    pat = re.compile(r"万円|物件|No|№|売買|賃貸")
    seen = 0
    for el in soup.find_all(string=pat):
        parent = el.parent
        chain = []
        node = parent
        for _ in range(4):
            if node is None or node.name is None:
                break
            chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
            node = node.parent
        text = " ".join(str(el).split())[:50]
        print(f"  [{text}] 祖先: {' < '.join(chain)}")
        seen += 1
        if seen >= 25:
            break
    # 表があれば先頭の表をダンプ
    table = soup.find("table")
    if table is not None:
        print("--- 最初の<table>の先頭部分 ---")
        print(table.prettify()[:5000])
    else:
        print("(tableなし。本文の先頭を表示)")
        main = soup.find("div", id="main") or soup.body
        print(main.get_text("\n", strip=True)[:3000])


def main() -> None:
    for source_id, url in ATHOME_CANDIDATES:
        test_athome(source_id, url)
    recon_kirishima()
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
