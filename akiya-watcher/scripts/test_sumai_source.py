"""新規情報源の接続テスト 第3弾: 家いちば・みんなの0円物件・鹿児島市空き家バンク。

各サイトについて robots.txt / RSSフィードの有無 / 一覧ページの様子を確認する。
DB・通知は使わない読み取りテストのみ。
"""
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, ".")

import requests

UA = {"User-Agent": "akiya-watcher/0.1 (personal use)"}

TARGETS = [
    {
        "name": "家いちば",
        "robots": "https://www.ieichiba.com/robots.txt",
        "feeds": ["https://www.ieichiba.com/feed",
                  "https://www.ieichiba.com/rss",
                  "https://www.ieichiba.com/new.rss"],
        "pages": ["https://www.ieichiba.com/new"],
    },
    {
        "name": "みんなの0円物件",
        "robots": "https://zero.estate/robots.txt",
        "feeds": ["https://zero.estate/feed"],
        "pages": ["https://zero.estate/category/zero/kyushu/kagoshima/",
                  "https://zero.estate/category/zero/kyushu/miyazaki/"],
    },
    {
        "name": "鹿児島市空き家バンク(アットホーム基盤)",
        "robots": "https://kagoshima-c46201.akiya-athome.jp/robots.txt",
        "feeds": [],
        "pages": ["https://kagoshima-c46201.akiya-athome.jp/"],
    },
]


def show_feed(url: str) -> None:
    try:
        r = requests.get(url, timeout=20, headers=UA)
        print(f"  feed {url} → status {r.status_code}, bytes {len(r.content)}")
        if r.status_code != 200:
            return
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            print("    (XMLではない)")
            return
        items = root.findall(".//item")
        print(f"    item数: {len(items)}")
        for item in items[:6]:
            t = (item.findtext("title") or "").strip()
            print(f"    ・{t[:80]}")
    except Exception as e:
        print(f"  feed {url} → 失敗: {type(e).__name__}: {e}")


def show_page(url: str) -> None:
    try:
        r = requests.get(url, timeout=20, headers=UA)
        text = r.text
        price_hits = text.count("万円") + text.count("0円")
        print(f"  page {url} → status {r.status_code}, bytes {len(r.content)},"
              f" 価格らしき表記 {price_hits}箇所")
    except Exception as e:
        print(f"  page {url} → 失敗: {type(e).__name__}: {e}")


for t in TARGETS:
    print(f"\n===== {t['name']} =====")
    try:
        r = requests.get(t["robots"], timeout=20, headers=UA)
        body = r.text[:600] if r.status_code == 200 else f"(status {r.status_code})"
        print(f"robots.txt:\n{body}")
    except Exception as e:
        print(f"robots.txt 取得失敗: {e}")
    for f in t["feeds"]:
        show_feed(f)
    for p in t["pages"]:
        show_page(p)

print("\n===== テスト終了 =====")
