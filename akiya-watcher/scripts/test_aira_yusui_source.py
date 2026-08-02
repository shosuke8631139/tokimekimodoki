"""偵察: 都城市の空き家バンク移行先「住めば住むほど都城」の構造確認。

判明事項: 都城のアットホーム系サイト(miyakonojo-c45202)は空。
本当の物件は移住特設サイト sumeba-sumuhodo-miyakonojo.jp の
/residence/ 配下に「【管理番号280】空き家（梅北町）」形式で載っている。
robots.txt と一覧ページの構造を確認する。
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
BASE = "https://www.sumeba-sumuhodo-miyakonojo.jp"

CANDIDATES = [
    "/residence/",
    "/category/residence/",
    "/akiya/",
]


def robots() -> None:
    print("=" * 78)
    print("### robots.txt")
    try:
        r = requests.get(BASE + "/robots.txt", timeout=20, headers=UA)
        print(f"status={r.status_code}")
        print(r.text[:600])
    except Exception as exc:  # noqa: BLE001
        print(f"取得失敗: {exc}")


def dump_cards() -> None:
    """一覧の物件カード構造を丸ごとダンプ (リンクはURL側に管理番号がある)。"""
    print("=" * 78)
    print("### /residence/ 物件カードのダンプ")
    r = requests.get(BASE + "/residence/", timeout=30, headers=UA)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    from urllib.parse import unquote
    cards = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/residence/" not in href:
            continue
        decoded = unquote(href)
        if "管理番号" not in decoded and "%e7%ae%a1" not in href.lower():
            continue
        if href in seen:
            continue
        seen.add(href)
        cards.append((a, decoded))
    print(f"物件詳細リンク: {len(cards)}件")
    for a, decoded in cards[:8]:
        print(f"  {decoded[:90]}")
    if cards:
        a = cards[0][0]
        node = a
        for _ in range(4):
            if node.parent is not None and node.parent.name not in ("body", "html"):
                node = node.parent
        print("--- 最初のカードの構造 (親4段) ---")
        print(node.prettify()[:3500])


def probe(path: str) -> None:
    print("=" * 78)
    print(f"### {BASE}{path}")
    try:
        r = requests.get(BASE + path, timeout=30, headers=UA)
        r.encoding = "utf-8"
    except Exception as exc:  # noqa: BLE001
        print(f"!! {exc}")
        return
    print(f"status={r.status_code} bytes={len(r.text)}")
    if r.status_code != 200:
        return
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "?"
    print(f"title={title[:60]}")

    # 物件リンク (管理番号◯◯) を数える
    links = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if re.search(r"管理番号|空き家|空家", text):
            links.append((text[:50], a["href"]))
    print(f"物件らしきリンク: {len(links)}件")
    for text, href in links[:10]:
        print(f"  [{text}] {href[:90]}")

    # カード構造の観察 (最初の物件リンクの祖先をダンプ)
    if links:
        first = soup.find("a", string=re.compile("管理番号"))
        if first is None:
            for a in soup.find_all("a", href=True):
                if "管理番号" in a.get_text():
                    first = a
                    break
        if first is not None:
            node = first
            for _ in range(3):
                if node.parent is not None and node.parent.name not in ("body", "html"):
                    node = node.parent
            print("--- 物件カードとおぼしき構造 ---")
            print(node.prettify()[:2500])

    # 価格・間取りの気配
    hits = 0
    for s in soup.find_all(string=re.compile("万円|価格|賃料")):
        node = s.parent
        chain = []
        for _ in range(3):
            if node is None or node.name is None:
                break
            chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
            node = node.parent
        print(f"  [{' '.join(str(s).split())[:35]}] {' < '.join(chain)}")
        hits += 1
        if hits >= 8:
            break
    # ページ送りの気配
    for a in soup.find_all("a", href=True):
        if re.search(r"page|次へ|next|2", a.get("href", "")) and re.search(
                r"/residence|page", a["href"]):
            print(f"  ページ送り候補: {a['href'][:80]}")
            break


def main() -> None:
    dump_cards()
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
