"""巡回網拡張②〜④の一括偵察: 鹿屋・出水・伊佐・曽於・都城(新型アットホーム)。

姶良(aira-c46225)で解読済みの構造が5市にも当てはまるかを一括確認する。
手順: 各サイトの /buy/house/area/ から「〇〇市」リンク(list?gyosei_cd)を
自動発見 → 一覧を取得 → 姶良と同じセレクタで読めるか検証 →
ページング(表示件数)の仕組みも観察する。
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}

SITES = [
    ("kanoya", "https://kanoya-c46203.akiya-athome.jp"),
    ("izumi", "https://izumi-c46208.akiya-athome.jp"),
    ("isa", "https://isa-c46224.akiya-athome.jp"),
    ("soo", "https://soo-c46217.akiya-athome.jp"),
    ("miyakonojo", "https://miyakonojo-c45202.akiya-athome.jp"),
]


def probe(name: str, base: str) -> None:
    print("=" * 78)
    print(f"### {name} {base}")
    # 1. エリア検索ページから一覧URLを自動発見
    try:
        r1 = requests.get(base + "/buy/house/area/", timeout=30, headers=UA)
        r1.encoding = "utf-8"
    except Exception as exc:  # noqa: BLE001
        print(f"!! エリアページ取得失敗: {exc}")
        return
    soup1 = BeautifulSoup(r1.text, "html.parser")
    list_url = None
    for a in soup1.find_all("a", href=True):
        if "list?gyosei_cd" in a["href"]:
            list_url = a["href"] if a["href"].startswith("http") else base + a["href"]
            print(f"一覧URL発見: [{a.get_text(strip=True)[:20]}] {list_url}")
            break
    if list_url is None:
        print("!! 一覧URLが見つからない。エリアページのリンクを表示:")
        for a in soup1.find_all("a", href=True)[:30]:
            t = " ".join(a.get_text(" ", strip=True).split())[:30]
            if "/buy/" in a["href"] or "list" in a["href"]:
                print(f"  [{t}] {a['href']}")
        return

    time.sleep(1)
    # 2. 一覧を取得して姶良と同じセレクタで検証
    try:
        r2 = requests.get(list_url, timeout=30, headers=UA)
        r2.encoding = "utf-8"
    except Exception as exc:  # noqa: BLE001
        print(f"!! 一覧取得失敗: {exc}")
        return
    soup2 = BeautifulSoup(r2.text, "html.parser")
    items = soup2.select("ul.property-list-one > li")
    print(f"property-list-one > li: {len(items)}件")
    for li in items[:4]:
        name_a = li.select_one("dt a")
        price = li.select_one("td.price-strong")
        addr = li.select_one('li[data-column="address"]')
        madori = li.select_one('td[data-column="madori"]')
        print(f"  [{name_a.get_text(strip=True)[:30] if name_a else '?'}] "
              f"{price.get_text(' ', strip=True) if price else '?'} "
              f"{madori.get_text(strip=True) if madori else '?'} "
              f"{addr.get_text(' ', strip=True) if addr else '?'}")
        if name_a:
            print(f"      {name_a.get('href')}")
    # 3. ページング(表示件数)の仕組みを観察
    pg = soup2.select_one(".pagination-item-count") or soup2.select_one(".pagenation-input")
    if pg is not None:
        print("--- 表示件数UI ---")
        print(pg.prettify()[:1200])
    # 全件表示のヒント: limit/件数系のリンク・フォーム
    for a in soup2.find_all("a", href=True):
        if re.search(r"limit|count|100", a["href"]):
            print(f"  件数リンク候補: [{a.get_text(strip=True)[:15]}] {a['href']}")


def main() -> None:
    for name, base in SITES:
        probe(name, base)
        time.sleep(1)
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
