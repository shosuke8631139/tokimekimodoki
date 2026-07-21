"""Sumai空き家 接続テスト (GitHub Actionsから手動実行)。

やること:
  1. robots.txt を取得して内容を表示 (自動アクセスが許可されているか)
  2. 鹿児島・宮崎の一覧ページ候補を1回ずつ取得し、物件タイトルが
     解析できるかを表示 (DBも通知も使わない読み取りテストのみ)

このテストの結果を見て、config.yaml の sumai_akiya ソースを
有効化するかを判断する。
"""
import sys

sys.path.insert(0, ".")

import requests

from akiya_watcher.scrapers.sumai_akiya import SumaiAkiyaScraper

ROBOTS = "https://akiya.sumai.biz/robots.txt"
CANDIDATE_URLS = [
    "https://akiya.sumai.biz/kyushu-kagoshima-akiyabank",
    "https://akiya.sumai.biz/kagoshima-akiya",
    "https://akiya.sumai.biz/kyushu-miyazaki-akiyabank",
    "https://akiya.sumai.biz/miyazaki-akiya",
]

print("===== 1. robots.txt =====")
try:
    r = requests.get(ROBOTS, timeout=20,
                     headers={"User-Agent": "akiya-watcher/0.1 (personal use)"})
    print(f"status: {r.status_code}")
    print(r.text[:1500] or "(空)")
except Exception as e:
    print(f"取得失敗: {e}")

print()
print("===== 2. 一覧ページの読み取りテスト =====")
for url in CANDIDATE_URLS:
    print(f"\n--- {url}")
    try:
        scraper = SumaiAkiyaScraper({"id": "sumai_test", "list_urls": [url]})
        listings = scraper.fetch_listings()
        print(f"物件として解析できた件数: {len(listings)}")
        for ls in listings[:5]:
            price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格不明"
            drop = (f" (変更前 {ls.advertised_previous_price_yen:,}円)"
                    if ls.advertised_previous_price_yen else "")
            print(f"  ・{price}{drop} {ls.title[:70]}")
    except PermissionError as e:
        print(f"robots.txt により取得禁止: {e}")
    except Exception as e:
        print(f"取得失敗: {type(e).__name__}: {e}")

print("\n===== テスト終了 =====")
