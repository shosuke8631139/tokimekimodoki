"""偵察: 都城の物件詳細ページの価格表記を確認する。

ユーザー報告: メールでは価格不明だが、実ページには価格が表示されている。
→ parse_detail の価格パターンが実表記と合っていない。実物を見て合わせる。
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}
DETAIL = ("https://www.sumeba-sumuhodo-miyakonojo.jp/residence/"
          "%E3%80%90%E7%AE%A1%E7%90%86%E7%95%AA%E5%8F%B7421%E3%80%91"
          "%E5%A3%B2%E8%B2%B7%EF%BC%88%E8%93%91%E5%8E%9F%E7%94%BA%EF%BC%89/")


def main() -> None:
    r = requests.get(DETAIL, timeout=30, headers=UA)
    r.encoding = "utf-8"
    print(f"status={r.status_code} bytes={len(r.text)}")
    soup = BeautifulSoup(r.text, "html.parser")

    # 「円」「価格」「万」を含むテキストの前後を表示
    text = unicodedata.normalize("NFKC", soup.get_text(" ", strip=True))
    print("--- 「万」「円」「価格」の周辺 ---")
    for m in re.finditer(r"価格|万円|[0-9,]{3,}円|金額", text):
        s = max(0, m.start() - 40)
        print(f"  …{text[s:m.end() + 40]}…")

    # 定義リスト・表の構造 (価格がどのタグに入っているか)
    print("--- dl/dt/dd ---")
    for dl in soup.find_all("dl")[:6]:
        print("  " + " | ".join(" ".join(x.get_text(' ', strip=True).split())[:30]
                                for x in dl.find_all(["dt", "dd"])[:8]))
    print("--- table行 ---")
    for tr in soup.find_all("tr")[:12]:
        cells = [" ".join(c.get_text(" ", strip=True).split())[:30]
                 for c in tr.find_all(["th", "td"])]
        if cells:
            print("  " + " | ".join(cells))
    # 見出し・強調
    print("--- h2/h3/strong/span(価格らしきもの) ---")
    for el in soup.find_all(["h2", "h3", "strong", "p", "span", "div"]):
        t = " ".join(el.get_text(" ", strip=True).split())
        if re.search(r"[0-9,]+\s*万円|価格", t) and len(t) < 60:
            print(f"  <{el.name} class={el.get('class')}> {t}")


if __name__ == "__main__":
    main()
