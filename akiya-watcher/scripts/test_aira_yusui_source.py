"""巡回網拡張の偵察(5回目・決定打): 「売戸建0件」仮説の検証。

同システムの出水・姶良はサーバー描画で読めた。4市の売戸建一覧が空なのは
「JSの壁」ではなく「掲載が本当に0件」ではないか?
→ 物件が確実に存在する伊佐の賃貸一覧が素のHTTPで読めるかで判定する。
  読めれば: システムは読める・売戸建が空なだけ → configに登録しておけば
  掲載された瞬間に自動で拾える。
あわせて出水の2ページ目(page=2)の中身も確認する。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}

RENT_LISTS = [
    ("isa(賃貸)", "https://isa-c46224.akiya-athome.jp/rent/live/area/kagoshimaken/isashi/list?gyosei_cd[]=46224"),
    ("kanoya(賃貸)", "https://kanoya-c46203.akiya-athome.jp/rent/live/area/kagoshimaken/kanoyashi/list?gyosei_cd[]=46203"),
    ("soo(賃貸)", "https://soo-c46217.akiya-athome.jp/rent/live/area/kagoshimaken/sooshi/list?gyosei_cd[]=46217"),
    ("miyakonojo(賃貸)", "https://miyakonojo-c45202.akiya-athome.jp/rent/live/area/miyazakiken/miyakonojoshi/list?gyosei_cd[]=45202"),
    ("izumi(売買p2)", "https://izumi-c46208.akiya-athome.jp/buy/house/area/kagoshimaken/izumishi/list?gyosei_cd[]=46208&page=2"),
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
    for li in items[:5]:
        a = li.select_one("dt a")
        price = li.select_one("td.price-strong")
        addr = li.select_one('li[data-column="address"]')
        print(f"  [{a.get_text(strip=True)[:30] if a else '?'}] "
              f"{price.get_text(' ', strip=True) if price else '?'} "
              f"{addr.get_text(' ', strip=True) if addr else '?'}")
        if a:
            print(f"      {a.get('href')}")


def main() -> None:
    for name, url in RENT_LISTS:
        probe(name, url)
        time.sleep(1)
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
