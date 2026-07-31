"""さつま町 空き家情報バンク(売買)ページの構造偵察。

スクレイパー実装のための下調べ:
  1. robots.txt の内容
  2. 物件見出し(No.xxx 【売買】)がどのタグ/クラスに乗っているか
  3. 先頭2物件ぶんの生HTML(整形)
をログに出す。読み取り専用テスト。
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

UA = "akiya-watcher/0.1 (personal use; structure test)"
LIST_URL = "https://www.satsuma-net.jp/teiju/akiya/1/5623.html"
ROBOTS = "https://www.satsuma-net.jp/robots.txt"

HEAD_PAT = re.compile(r"N[Oo]\.?\s*\d+")


def main() -> None:
    print("### robots.txt")
    try:
        r = requests.get(ROBOTS, headers={"User-Agent": UA}, timeout=30)
        print(f"status={r.status_code}")
        print(r.text[:1500] or "(空)")
    except Exception as exc:  # noqa: BLE001
        print(f"取得失敗: {exc}")

    print("### 一覧ページ取得")
    res = requests.get(LIST_URL, headers={"User-Agent": UA}, timeout=30)
    res.encoding = res.apparent_encoding
    print(f"status={res.status_code} bytes={len(res.text)}")
    soup = BeautifulSoup(res.text, "html.parser")

    print("### 『No.xxx』を含む要素のタグ構造 (先頭10件)")
    seen = 0
    for el in soup.find_all(string=HEAD_PAT):
        parent = el.parent
        chain = []
        node = parent
        for _ in range(4):
            if node is None or node.name is None:
                break
            chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
            node = node.parent
        text = " ".join(str(el).split())[:40]
        print(f"  [{text}] 祖先: {' < '.join(chain)}")
        seen += 1
        if seen >= 10:
            break

    print("### 本文コンテンツ領域の候補と、先頭2物件の生HTML")
    # 「No.186」など最初の見出しを含む親ブロックを遡って特定する
    first = soup.find(string=re.compile(r"No\.?\s*18\d"))
    if first is None:
        first = soup.find(string=HEAD_PAT)
    if first is None:
        print("見出しが見つからない")
        return
    block = first.parent
    for _ in range(6):
        if block.parent is None:
            break
        # 物件見出しを2つ以上含むところまで遡る = 一覧のコンテナ
        if len(block.find_all(string=HEAD_PAT)) >= 4:
            break
        block = block.parent
    print(f"コンテナ: <{block.name} class={block.get('class')}>")
    html = block.prettify()
    print(html[:9000])


if __name__ == "__main__":
    main()
