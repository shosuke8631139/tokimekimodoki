"""Sumai空き家 接続テスト 第2弾 (GitHub Actionsから手動実行)。

第1弾の結果: robots.txt は /wp-admin/ 以外を許可。RSS(sitemap.rss)の存在を確認。
今回はRSSフィードの中身と、市町村ページの物件解析を確認する。
"""
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, ".")

import requests

from akiya_watcher.scrapers.sumai_akiya import SumaiAkiyaScraper, parse_listing_title

UA = {"User-Agent": "akiya-watcher/0.1 (personal use)"}

FEEDS = [
    "https://akiya.sumai.biz/sitemap.rss",
    "https://akiya.sumai.biz/feed",
]

print("===== 1. RSSフィードの中身 =====")
for feed_url in FEEDS:
    print(f"\n--- {feed_url}")
    try:
        r = requests.get(feed_url, timeout=20, headers=UA)
        print(f"status: {r.status_code}, bytes: {len(r.content)}")
        if r.status_code != 200:
            continue
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        print(f"item数: {len(items)}")
        for item in items[:12]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            parsed = parse_listing_title(title)
            mark = "◎物件" if parsed else "  --"
            drop = ""
            if parsed and parsed.get("advertised_previous_price_yen"):
                drop = " 🔻値下げ検知可"
            print(f"  {mark}{drop} [{pub[:16]}] {title[:80]}")
            if parsed:
                print(f"        → 価格:{parsed['price_yen']} 住所:{parsed['address']}")
    except Exception as e:
        print(f"取得失敗: {type(e).__name__}: {e}")

print("\n===== 2. 市町村ページの物件解析 =====")
for url in ["https://akiya.sumai.biz/kagoshima-akiya/kagoshima-satsuma"]:
    print(f"\n--- {url}")
    try:
        scraper = SumaiAkiyaScraper({"id": "sumai_test", "list_urls": [url]})
        listings = scraper.fetch_listings()
        print(f"物件として解析できた件数: {len(listings)}")
        for ls in listings[:5]:
            price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格不明"
            print(f"  ・{price} {ls.title[:70]}")
    except Exception as e:
        print(f"取得失敗: {type(e).__name__}: {e}")

print("\n===== テスト終了 =====")
