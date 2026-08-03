"""偵察第2弾: 薩摩川内CGI一覧と日置地域ページの実物構造 (2026-08-03)。

第1弾の発見:
  - 薩摩川内市サイトに独自の一覧CGIがある (athome系3件とは別の可能性)
    https://www.city.satsumasendai.lg.jp/cgi-bin/recruit.php/3/list
  - 日置市バンクは地域別4ページ構成 (東市来/伊集院/日吉/吹上)
この2つの中身(件数・価格表記・1件分のHTML構造)を確認する。
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
    ("薩摩川内CGI一覧",
     "https://www.city.satsumasendai.lg.jp/cgi-bin/recruit.php/3/list"),
    ("日置市: 東市来地域",
     "https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/akiyabank/akiyabank_higashiichiki.html"),
    ("日置市: 吹上地域",
     "https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/akiyabank/akiyabank_fukiage.html"),
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

    prices = re.findall(r"[0-9,.]+\s*万円|[0-9]{1,3}(?:,[0-9]{3})+\s*円", text)
    print(f"  価格らしい表記: {len(prices)}件  例: {prices[:10]}")
    for kw in ("売買", "賃貸", "売却", "成約", "交渉中"):
        print(f"  「{kw}」出現: {len(re.findall(kw, text))}回")

    # 物件1件分がどのタグに入っているか: 詳細リンクの型
    hits = []
    for a in soup.find_all("a", href=True):
        t = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(url, a["href"])
        if re.search(r"detail|物件|No\.?\s*[0-9]|[0-9]{2,}", t + href):
            hits.append(f"{t[:35]} -> {href}")
    print(f"  詳細ページらしいリンク: {len(hits)}件 (先頭12件)")
    for h in hits[:12]:
        print(f"    {h}")

    # 一覧の構造
    print("  --- table行(先頭12) ---")
    for tr in soup.find_all("tr")[:12]:
        cells = [" ".join(c.get_text(" ", strip=True).split())[:25]
                 for c in tr.find_all(["th", "td"])]
        if cells:
            print("    " + " | ".join(cells))
    print("  --- 主要ブロックのclass名 ---")
    seen = {}
    for el in soup.find_all(["div", "ul", "li", "section", "article"]):
        cls = " ".join(el.get("class") or [])
        if cls:
            seen[cls] = seen.get(cls, 0) + 1
    for cls, n in sorted(seen.items(), key=lambda x: -x[1])[:12]:
        print(f"    .{cls} ×{n}")


def main() -> None:
    for name, url in TARGETS:
        probe(name, url)


if __name__ == "__main__":
    main()
