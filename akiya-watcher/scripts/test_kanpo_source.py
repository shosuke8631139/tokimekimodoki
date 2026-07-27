"""接続テスト第6弾: Sumai空き家の個別物件ページの追跡可否と構造採取。

目的:
  1. akiya.sumai.biz の robots.txt が今朝クラウドから読めなかった件の再確認
     (一時的なものか、恒常的なブロックか)
  2. ユーザー指名物件 https://akiya.sumai.biz/117604 のページ構造採取
     (タイトル・価格・住所・説明文・掲載終了時の見え方の設計材料)
"""
import re
import time

import requests

UA = {"User-Agent": "akiya-watcher/0.1 (personal use)"}
BASE = "https://akiya.sumai.biz"
TARGET = f"{BASE}/122604"


def fetch(url: str):
    time.sleep(3)
    try:
        r = requests.get(url, timeout=20, headers=UA)
        print(f"  GET {url} -> {r.status_code} "
              f"({r.headers.get('Content-Type', '?')}, {len(r.content):,} bytes)")
        return r
    except Exception as e:
        print(f"  GET {url} -> 失敗 {type(e).__name__}: {e}")
        return None


print("===== 1. robots.txt の状態 =====")
r = fetch(f"{BASE}/robots.txt")
if r is not None:
    print("  冒頭15行:")
    for line in r.text.splitlines()[:15]:
        print(f"    {line}")

print("\n===== 2. RSSフィードの状態 (今朝0件だった件) =====")
r = fetch(f"{BASE}/feed")
if r is not None and r.status_code == 200:
    print(f"  <item> の数: {r.text.count('<item>')}")

print("\n===== 3. 指名物件ページの採取 =====")
r = fetch(TARGET)
if r is not None and r.status_code == 200:
    html = r.text
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    print(f"  タイトル: {m.group(1).strip() if m else '?'}")
    for prop in ("og:title", "og:description", "og:url"):
        m = re.search(rf'property="{prop}"\s+content="([^"]*)"', html)
        if not m:
            m = re.search(rf'content="([^"]*)"\s+property="{prop}"', html)
        print(f"  {prop}: {m.group(1)[:300] if m else '(なし)'}")
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    print(f"  本文文字数: {len(text)}")
    print("  本文の先頭1200文字:")
    print("  " + text[:1200])
    for kw in ("万円", "残置物", "家財", "蔵", "相続", "現状", "成約", "掲載終了",
               "問い合わせ", "駐車"):
        print(f"  「{kw}」出現: {text.count(kw)}回")

print("\n===== 4. 存在しないIDの見え方 (掲載終了検知の設計用) =====")
r = fetch(f"{BASE}/999999999")
if r is not None:
    print(f"  ステータス: {r.status_code} (404なら判定は簡単)")

print("\n===== テスト終了 =====")
