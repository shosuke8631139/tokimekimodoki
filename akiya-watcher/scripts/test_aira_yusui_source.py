"""巡回網拡張の偵察(2回目): 直接URL方式+表示件数パラメータの探索。

判明: 新型アットホームの一覧URLは
  {site}/buy/house/area/{kenローマ字}/{市ローマ字}shi/list?gyosei_cd[]={市コード}
の規則。エリアページにリンクが出ないサイトがあるため直接叩く。
出水は21件中20件しか出ない(表示件数selectはJS)ため、
クエリパラメータで100件表示にできるか候補を試す。
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
    ("kanoya", "https://kanoya-c46203.akiya-athome.jp/buy/house/area/kagoshimaken/kanoyashi/list?gyosei_cd[]=46203"),
    ("isa", "https://isa-c46224.akiya-athome.jp/buy/house/area/kagoshimaken/isashi/list?gyosei_cd[]=46224"),
    ("soo", "https://soo-c46217.akiya-athome.jp/buy/house/area/kagoshimaken/sooshi/list?gyosei_cd[]=46217"),
    ("miyakonojo", "https://miyakonojo-c45202.akiya-athome.jp/buy/house/area/miyazakiken/miyakonojoshi/list?gyosei_cd[]=45202"),
]

IZUMI = "https://izumi-c46208.akiya-athome.jp/buy/house/area/kagoshimaken/izumishi/list?gyosei_cd[]=46208"


def count_items(url: str) -> tuple[int, BeautifulSoup | None]:
    try:
        res = requests.get(url, timeout=30, headers=UA)
        res.encoding = "utf-8"
    except Exception as exc:  # noqa: BLE001
        print(f"  !! 取得失敗: {exc}")
        return -1, None
    soup = BeautifulSoup(res.text, "html.parser")
    return len(soup.select("ul.property-list-one > li")), soup


def probe(name: str, url: str) -> None:
    print("=" * 78)
    print(f"### {name}")
    n, soup = count_items(url)
    print(f"{url}\n  → {n}件")
    if soup is None or n <= 0:
        return
    for li in soup.select("ul.property-list-one > li")[:4]:
        a = li.select_one("dt a")
        price = li.select_one("td.price-strong")
        addr = li.select_one('li[data-column="address"]')
        madori = li.select_one('td[data-column="madori"]')
        print(f"  [{a.get_text(strip=True)[:30] if a else '?'}] "
              f"{price.get_text(' ', strip=True) if price else '?'} "
              f"{madori.get_text(strip=True) if madori else '?'} "
              f"{addr.get_text(' ', strip=True) if addr else '?'}")
    # 総件数の表示(「◯棟」等)があれば拾う
    for s in soup.stripped_strings:
        if ("棟" in s or "該当" in s) and any(c.isdigit() for c in s):
            print(f"  件数表示らしき文言: {s[:40]}")
            break


def probe_limit_params() -> None:
    print("=" * 78)
    print("### 出水: 表示件数パラメータの探索 (現状20件/実物21件)")
    for param in ["&limit=100", "&pageD=100", "&count=100", "&disp=100",
                  "&view=100", "&per_page=100"]:
        n, _ = count_items(IZUMI + param)
        print(f"  {param}: {n}件")
        time.sleep(1)
    # ページ2の形式も試す
    for suffix in ["&page=2", "&p=2"]:
        n, _ = count_items(IZUMI + suffix)
        print(f"  {suffix}: {n}件")
        time.sleep(1)


def main() -> None:
    for name, url in LISTS:
        probe(name, url)
        time.sleep(1)
    probe_limit_params()
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
