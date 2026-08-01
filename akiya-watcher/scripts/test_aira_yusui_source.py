"""巡回先拡張の偵察3回目: 姶良市 /buy/house/area/ 深掘り+湧水アダプタ実地検証。

前回までの判明事項:
- 姶良市 aira-c46225.akiya-athome.jp はメニュー型の新型athomeサイト。
  一覧は /buy/house/area/ /buy/land/area/ 等の配下にある想定。
- 湧水町は構造解読済み→アダプタ実装済み。本物のページで検証する。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from akiya_watcher.scrapers.yusui_bank import YusuiBankScraper  # noqa: E402

AIRA = "https://aira-c46225.akiya-athome.jp"
YUSUI_AKIYA = "https://www.town.yusui.kagoshima.jp/soshiki/34/787.html"
UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}

ATHOME_FIELDS = {
    "title":       {"selector": ".property-name a", "attr": "text"},
    "url":         {"selector": ".property-name a", "attr": "href"},
    "price":       {"selector": "dl.bukken-info dd.price-strong", "attr": "text"},
    "layout":      {"selector": "dl.bukken-info dd:nth-of-type(2)", "attr": "text"},
    "land_area":   {"selector": "dl.bukken-info dd:nth-of-type(3)", "attr": "text"},
    "address":     {"selector": "dl.bukken-info dd:nth-of-type(4)", "attr": "text"},
    "description": {"selector": "dl.bukken-info", "attr": "text"},
}


def probe_aira(path: str) -> None:
    url = AIRA + path
    print("=" * 78)
    print(f"### 姶良 {url}")
    try:
        res = requests.get(url, timeout=30, headers=UA)
    except Exception as exc:  # noqa: BLE001
        print(f"!! 取得失敗: {exc}")
        return
    res.encoding = res.apparent_encoding
    print(f"status={res.status_code} bytes={len(res.text)}")
    soup = BeautifulSoup(res.text, "html.parser")

    # 既存セレクタ(鹿児島市と同じ)での一致数を直接確認
    items = soup.select("ul.property-simple > li")
    print(f"property-simple: {len(items)}件")
    for li in items[:5]:
        name = li.select_one(".property-name a")
        price = li.select_one("dl.bukken-info dd.price-strong")
        print(f"  [{name.get_text(strip=True)[:40] if name else '?'}] "
              f"{price.get_text(strip=True) if price else '?'} "
              f"{name.get('href') if name else ''}")

    # 物件らしき要素のクラス名を観察
    print("--- クラス観察 (property/bukken/item/card/list) ---")
    for el in soup.find_all(class_=re.compile("property|bukken|item|card|result"))[:12]:
        print(f"  <{el.name} class={el.get('class')}> "
              f"{' '.join(el.get_text(' ', strip=True).split())[:70]}")
    # 万円を含むテキストの祖先
    print("--- 「万円」を含む要素の祖先 ---")
    seen = 0
    for s in soup.find_all(string=re.compile("万円")):
        node = s.parent
        chain = []
        for _ in range(4):
            if node is None or node.name is None:
                break
            chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
            node = node.parent
        print(f"  [{' '.join(str(s).split())[:40]}] {' < '.join(chain)}")
        seen += 1
        if seen >= 10:
            break
    # ページ内リンク (一覧ページへの導線)
    print("--- リンク (エリア・一覧候補) ---")
    for a in soup.find_all("a", href=True)[:40]:
        text = " ".join(a.get_text(" ", strip=True).split())[:30]
        if re.search(r"area|list|検索|一覧|件", text + a["href"]):
            print(f"  [{text}] {a['href']}")


def verify_yusui() -> None:
    print("=" * 78)
    print("### 湧水町 アダプタ実地検証")
    scraper = YusuiBankScraper({"id": "yusui_akiya_bank", "list_url": YUSUI_AKIYA})
    try:
        listings = scraper.fetch_listings()
    except Exception as exc:  # noqa: BLE001
        print(f"!! 取得失敗: {exc}")
        return
    print(f"読み取り: {len(listings)}件 (売買のみ)")
    for l in listings:
        price = f"{l.price_yen:,}円" if l.price_yen is not None else "応相談"
        print(f"  {l.listing_id}: {price} {l.address} | {l.url}")


def main() -> None:
    # 3回目で発見した「姶良市」リンクの一覧本体を精査する
    probe_aira("/buy/house/area/kagoshimaken/airashi/list?gyosei_cd[]=46225")
    probe_aira("/buy/land/area/kagoshimaken/airashi/list?gyosei_cd[]=46225")
    verify_yusui()
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
