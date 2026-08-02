"""巡回網拡張の偵察: 薩摩川内市・いちき串木野市(新型アットホーム)。

出水・姶良で実証済みの直接URL方式で売戸建一覧を確認する。
20件超なら page=2 も読む(出水と同じ)。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}

LISTS = [
    ("satsumasendai",
     "https://satsumasendai-c46215.akiya-athome.jp/buy/house/area/kagoshimaken/satsumasendaishi/list?gyosei_cd[]=46215"),
    ("satsumasendai(p2)",
     "https://satsumasendai-c46215.akiya-athome.jp/buy/house/area/kagoshimaken/satsumasendaishi/list?gyosei_cd[]=46215&page=2"),
    ("ichikikushikino",
     "https://ichikikushikino-c46219.akiya-athome.jp/buy/house/area/kagoshimaken/ichikikushikinoshi/list?gyosei_cd[]=46219"),
    ("ichikikushikino(p2)",
     "https://ichikikushikino-c46219.akiya-athome.jp/buy/house/area/kagoshimaken/ichikikushikinoshi/list?gyosei_cd[]=46219&page=2"),
]


def probe(name: str, url: str) -> None:
    print("=" * 78)
    print(f"### {name}")
    try:
        r = requests.get(url, timeout=30, headers=UA)
        r.encoding = "utf-8"
    except Exception as exc:  # noqa: BLE001
        print(f"!! {exc}")
        return
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("ul.property-list-one > li")
    print(f"status={r.status_code} property-list-one>li: {len(items)}件")
    for li in items[:6]:
        a = li.select_one("dt a")
        price = li.select_one("td.price-strong")
        addr = li.select_one('li[data-column="address"]')
        madori = li.select_one('td[data-column="madori"]')
        print(f"  [{a.get_text(strip=True)[:30] if a else '?'}] "
              f"{price.get_text(' ', strip=True) if price else '?'} "
              f"{madori.get_text(strip=True) if madori else '?'} "
              f"{addr.get_text(' ', strip=True) if addr else '?'}")


def main() -> None:
    for name, url in LISTS:
        probe(name, url)
        time.sleep(1)
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
