"""卒業制作図解v2の公開ページ(Netlify)を取得して監査する (2026-08-09)。

Claude Codeの実行環境からNetlifyへ直接アクセスできないため、
Actions経由で取得する。監査項目はユーザー指定のチェックリスト:
  1. KPI数字の一致 (22系統 / 121件 / 226件 / 4〜6回 / 月0円)
  2. 「5 v2での進化」章の有無
  3. 公開NGワード (公売・競売・差押・実在市町村名)
  4. 厚い内容の残存 (作品1/作品2/メールモック/⭐キープ/AIチーム運営/工夫と苦戦)
  5. 技術条件 (単一HTML・JSなし・CDNなし・外部フォント/画像なし・ダーク対応)

最後にHTML全文をbase64で出力する (リポジトリへ同期して直接修正するため)。
"""
from __future__ import annotations

import base64
import re
import sys

import requests

URL = "https://sotsusei-zukai-v2.netlify.app"


def main() -> int:
    res = requests.get(URL, timeout=30,
                       headers={"User-Agent": "akiya-watcher/0.1 (audit)"})
    html = res.text
    print(f"HTTP {res.status_code} / {len(html):,}文字 / "
          f"Content-Type: {res.headers.get('Content-Type')}")

    print("\n===== 1. KPI数字 =====")
    for kw in ("22", "121", "226", "4〜6", "月0円", "16", "56件", "162",
               "19系統", "90件"):
        print(f"  「{kw}」出現: {html.count(kw)}回")

    print("\n===== 2. 章立て =====")
    for m in re.finditer(r"<h([12])[^>]*>(.*?)</h\1>", html, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        print(f"  h{m.group(1)}: {text[:70]}")
    for m in re.finditer(r'class="sec-no"[^>]*>([^<]+)<', html):
        print(f"  sec-no: {m.group(1).strip()}")

    print("\n===== 3. 公開NGワード =====")
    for kw in ("公売", "競売", "差押", "入札"):
        n = html.count(kw)
        print(f"  「{kw}」出現: {n}回")
        if n:
            for mm in list(re.finditer(f".{{60}}{kw}.{{60}}", html))[:3]:
                clean = re.sub(r"<[^>]+>", " ", mm.group(0))
                print(f"    …{clean}…")
    for city in ("霧島市", "日置市", "薩摩川内市", "いちき串木野市", "さつま町",
                 "鹿児島市", "出水市", "姶良市", "湧水町", "伊佐市", "鹿屋市",
                 "都城市", "宮崎市", "曽於市"):
        n = html.count(city)
        if n:
            print(f"  市町村名「{city}」出現: {n}回")

    print("\n===== 4. 厚い内容の残存 =====")
    for kw in ("作品1", "作品2", "仕入れ点", "キープ", "AIチーム", "工夫", "苦戦",
               "巡回まとめ", "定期便"):
        print(f"  「{kw}」出現: {html.count(kw)}回")

    print("\n===== 5. 技術条件 =====")
    print(f"  <script>タグ: {len(re.findall(r'<script', html))}個")
    ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    print(f"  外部URL参照: {len(ext)}件")
    for u in ext[:10]:
        print(f"    {u}")
    print(f"  外部<img>: {len(re.findall(r'<img[^>]+src=\"http', html))}個")
    print(f"  prefers-color-scheme: {html.count('prefers-color-scheme')}回")
    print(f"  viewport meta: {'あり' if 'viewport' in html else 'なし'}")
    print(f"  table要素: {len(re.findall(r'<table', html))}個")
    print(f"  pre要素: {len(re.findall(r'<pre', html))}個")

    print("\n===== HTML全文 (base64) =====")
    b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    print("BEGIN_B64")
    for i in range(0, len(b64), 200):
        print(b64[i:i + 200])
    print("END_B64")
    return 0


if __name__ == "__main__":
    sys.exit(main())
