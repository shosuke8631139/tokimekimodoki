"""偵察: いちき串木野・薩摩川内の強化に伴う抜け漏れ確認 (2026-08-03)。

確認すること:
  1. 日置市: 独自の空き家バンク一覧ページ(市サイト)の構造。
     アットホーム系ではなく市直営の気配 → 湧水町パターンの可能性
  2. 薩摩川内市: 市サイト側に athome 系サイト以外の独自掲載があるか
     (都城の教訓: バンクが空でも実体が別サイトのことがある)
  3. ハトマークサイト(全宅連): 空き家バンク特集に川内・串木野の売戸建が
     載っている。robots.txt 的に読んでよいかだけ確認 (読むのはrobotsのみ)
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}

TARGETS = [
    ("日置市バンク一覧",
     "https://www.city.hioki.kagoshima.jp/kouho/ijuteju/akiya/akiyabank/index.html"),
    ("薩摩川内市サイト(空家バンク)",
     "https://www.city.satsumasendai.lg.jp/ijuteiju/sumai/2/index.html"),
    ("薩摩川内市サイト(制度ページ)",
     "https://www.city.satsumasendai.lg.jp/soshiki/1015/4/1/2/781.html"),
]

ROBOTS_ONLY = [
    ("ハトマークサイト", "https://www.hatomarksite.com/robots.txt"),
]


def probe(name: str, url: str) -> None:
    print(f"\n===== {name} =====\n{url}")
    try:
        r = requests.get(url, timeout=30, headers=UA)
    except Exception as e:
        print(f"  取得失敗: {type(e).__name__}: {e}")
        return
    r.encoding = r.apparent_encoding
    print(f"  status={r.status_code} bytes={len(r.text)}")
    if r.status_code != 200:
        return
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "(no title)"
    print(f"  title: {title}")
    text = unicodedata.normalize("NFKC", soup.get_text(" ", strip=True))

    prices = re.findall(r"[0-9,.]+\s*万円", text)
    print(f"  「万円」表記: {len(prices)}件  例: {prices[:8]}")

    # 物件らしいリンク (詳細ページの型を掴む)
    hits = []
    for a in soup.find_all("a", href=True):
        t = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(url, a["href"])
        if re.search(r"物件|空き家|空家|akiya|bukken", t + href, re.I):
            hits.append(f"{t[:40]} -> {href}")
    print(f"  物件らしいリンク: {len(hits)}件")
    for h in hits[:15]:
        print(f"    {h}")

    # 一覧の構造 (表 or カード)
    print("  --- table行(先頭) ---")
    for tr in soup.find_all("tr")[:8]:
        cells = [" ".join(c.get_text(" ", strip=True).split())[:25]
                 for c in tr.find_all(["th", "td"])]
        if cells:
            print("    " + " | ".join(cells))


def show_robots(name: str, url: str) -> None:
    print(f"\n===== {name} robots.txt =====\n{url}")
    try:
        r = requests.get(url, timeout=30, headers=UA)
        print(f"  status={r.status_code}")
        for line in r.text.splitlines()[:40]:
            print(f"  {line}")
    except Exception as e:
        print(f"  取得失敗: {type(e).__name__}: {e}")


def main() -> None:
    for name, url in TARGETS:
        probe(name, url)
    for name, url in ROBOTS_ONLY:
        show_robots(name, url)


if __name__ == "__main__":
    main()
