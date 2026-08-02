"""巡回網拡張の偵察(3回目): 鹿屋・伊佐・曽於・都城の「0件」の原因診断。

仮説A: 売戸建の掲載が本当に0件(サイトはあるが空)
仮説B: 別カテゴリ(土地・賃貸)や別サイト(市の公式ページ)に載っている
これを、ページの中身(タイトル・件数文言・カテゴリ別リンク)で判定する。
伊佐は市公式サイト(city.isa)にブログ形式の物件ページがある事も確認する。
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
    ("kanoya", "https://kanoya-c46203.akiya-athome.jp",
     "/buy/house/area/kagoshimaken/kanoyashi/list?gyosei_cd[]=46203"),
    ("isa", "https://isa-c46224.akiya-athome.jp",
     "/buy/house/area/kagoshimaken/isashi/list?gyosei_cd[]=46224"),
    ("soo", "https://soo-c46217.akiya-athome.jp",
     "/buy/house/area/kagoshimaken/sooshi/list?gyosei_cd[]=46217"),
    ("miyakonojo", "https://miyakonojo-c45202.akiya-athome.jp",
     "/buy/house/area/miyazakiken/miyakonojoshi/list?gyosei_cd[]=45202"),
]


def diagnose(name: str, base: str, path: str) -> None:
    print("=" * 78)
    print(f"### {name}")
    ses = requests.Session()
    ses.headers.update(UA)
    # 一覧ページの中身を診断
    r = ses.get(base + path, timeout=30)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "?"
    print(f"一覧: status={r.status_code} bytes={len(r.text)} title={title[:50]}")
    body_text = " ".join(soup.get_text(" ", strip=True).split())
    for pat in ["該当", "物件が見つかり", "ありません", "0件", "棟"]:
        m = re.search(rf".{{0,25}}{pat}.{{0,25}}", body_text)
        if m:
            print(f"  文言[{pat}]: …{m.group(0)}…")
    print(f"  property-list-one > li: {len(soup.select('ul.property-list-one > li'))}件")

    # トップページでカテゴリごとの掲載件数の気配を見る
    time.sleep(1)
    r2 = ses.get(base + "/", timeout=30)
    r2.encoding = "utf-8"
    s2 = BeautifulSoup(r2.text, "html.parser")
    print("  トップの新着・物件らしき要素:")
    for el in s2.find_all(class_=re.compile("new|property|bukken|list"))[:8]:
        txt = " ".join(el.get_text(" ", strip=True).split())[:70]
        if txt:
            print(f"    <{el.name} class={el.get('class')}> {txt}")
    # 万円を含む本文 (新着物件が載っていれば拾える)
    hits = 0
    for s in s2.find_all(string=re.compile("万円")):
        node = s.parent
        chain = []
        for _ in range(3):
            if node is None or node.name is None:
                break
            chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
            node = node.parent
        print(f"    [万円] {' '.join(str(s).split())[:40]} 祖先: {' < '.join(chain)}")
        hits += 1
        if hits >= 5:
            break
    if hits == 0:
        print("    (トップに価格表示なし)")


def recon_isa_city() -> None:
    print("=" * 78)
    print("### 伊佐市公式(city.isa)の空き家バンクページ")
    url = "https://www.city.isa.kagoshima.jp/teiju/bank/"
    try:
        r = requests.get(url, timeout=30, headers=UA)
        r.encoding = r.apparent_encoding
    except Exception as exc:  # noqa: BLE001
        print(f"!! 取得失敗: {exc}")
        return
    soup = BeautifulSoup(r.text, "html.parser")
    print(f"status={r.status_code} bytes={len(r.text)}")
    # 物件リンク(blog形式 No.xxx)を探す
    count = 0
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if re.search(r"No\.?\s*\d|物件|万円|空き家バンク", text):
            print(f"  [{text[:60]}] {a['href'][:80]}")
            count += 1
            if count >= 25:
                break
    if count == 0:
        print("  (物件らしきリンクなし。本文冒頭:)")
        print(" ".join(soup.get_text(" ", strip=True).split())[:800])


def main() -> None:
    for name, base, path in SITES:
        diagnose(name, base, path)
        time.sleep(1)
    recon_isa_city()
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
