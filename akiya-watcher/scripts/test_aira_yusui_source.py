"""巡回網拡張の偵察(4回目): JS描画サイトの抜け道2ルートの確認。

ルートA: アットホーム全国版 www.akiya-athome.jp の市コード指定一覧が
  サーバー描画なら、鹿屋・伊佐・曽於・都城を一括で読める。robots.txtも確認。
ルートB: 各市サイトのトップページに旧型カード(property-simple)で
  新着が載っている(伊佐で確認済み)。トップだけで何件見えるか数える。
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

GLOBAL = "https://www.akiya-athome.jp"
CITIES = [("kanoya", 46, 46203), ("isa", 46, 46224),
          ("soo", 46, 46217), ("miyakonojo", 45, 45202)]

TOPS = [
    ("kanoya", "https://kanoya-c46203.akiya-athome.jp/"),
    ("isa", "https://isa-c46224.akiya-athome.jp/"),
    ("soo", "https://soo-c46217.akiya-athome.jp/"),
    ("miyakonojo", "https://miyakonojo-c45202.akiya-athome.jp/"),
]


def route_a() -> None:
    print("=" * 78)
    print("### ルートA: 全国版 akiya-athome.jp")
    try:
        r = requests.get(GLOBAL + "/robots.txt", timeout=20, headers=UA)
        print(f"robots.txt status={r.status_code}")
        print(r.text[:800])
    except Exception as exc:  # noqa: BLE001
        print(f"robots.txt 取得失敗: {exc}")
    for name, pref, code in CITIES:
        url = (f"{GLOBAL}/bukken/search/list/?search_type=area"
               f"&br_kbn=buy&sbt_kbn=house&pref_cd={pref}&gyosei_cd[]={code}")
        time.sleep(1)
        try:
            r = requests.get(url, timeout=30, headers=UA)
            r.encoding = "utf-8"
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: !! {exc}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "?"
        n_new = len(soup.select("ul.property-list-one > li"))
        n_old = len(soup.select("ul.property-simple > li"))
        print(f"  {name}: status={r.status_code} bytes={len(r.text)} "
              f"title={title[:40]} list-one={n_new} simple={n_old}")
        # 万円を含む要素の祖先 (カード構造の当たりを付ける)
        hits = 0
        for s in soup.find_all(string=re.compile("万円")):
            node = s.parent
            chain = []
            for _ in range(4):
                if node is None or node.name is None:
                    break
                chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
                node = node.parent
            txt = " ".join(str(s).split())[:25]
            print(f"    [{txt}] {' < '.join(chain)}")
            hits += 1
            if hits >= 4:
                break
        if hits == 0:
            print("    (価格表示なし=こちらもJS描画の可能性)")


def route_b() -> None:
    print("=" * 78)
    print("### ルートB: 各市トップページの property-simple カード")
    for name, url in TOPS:
        time.sleep(1)
        try:
            r = requests.get(url, timeout=30, headers=UA)
            r.encoding = "utf-8"
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: !! {exc}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("ul.property-simple > li")
        print(f"--- {name}: property-simple > li = {len(items)}件 ---")
        for li in items[:10]:
            nm = li.select_one(".property-name")
            info = li.select_one("dl.bukken-info")
            print(f"  [{nm.get_text(' ', strip=True)[:25] if nm else '?'}] "
                  f"{' '.join(info.get_text(' ', strip=True).split())[:70] if info else ''}")
            a = li.select_one(".property-name a") or li.select_one("a")
            if a is not None:
                print(f"      {a.get('href')}")


def main() -> None:
    route_a()
    route_b()
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
