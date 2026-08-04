"""実地検証: さつま町の一覧1回と、300万円以下のPDF1件だけを読む。

本番DB・Gmailには触れない。BaseScraperの10秒間隔とrobots.txt確認を通し、
PDFから駐車台数・間取り・土地面積・建物面積のどれかを読めるか確認する。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.satsuma_bank import SatsumaBankScraper  # noqa: E402


def main() -> None:
    scraper = SatsumaBankScraper({
        "id": "satsuma_akiya_bank",
        "list_url": "https://www.satsuma-net.jp/teiju/akiya/1/5623.html",
    })
    listings = scraper.fetch_listings()
    candidates = [
        listing for listing in listings
        if listing.price_yen is not None
        and listing.price_yen <= 3_000_000
        and listing.url.lower().endswith(".pdf")
    ]
    print(f"一覧取得: {len(listings)}件 / 300万円以下PDF: {len(candidates)}件")
    if not candidates:
        raise SystemExit("確認できる300万円以下のPDF物件がありません")

    # アクセスを増やさないためPDFは先頭1件だけ読む。
    listing = scraper.enrich_listing(candidates[0])
    print(f"確認対象: {listing.listing_id} / {listing.price_yen:,}円")
    print(
        "PDF読取: "
        f"間取り={listing.layout or '不明'} / "
        f"駐車={listing.parking_slots if listing.parking_slots is not None else '不明'} / "
        f"土地={listing.land_area_sqm if listing.land_area_sqm is not None else '不明'} / "
        f"建物={listing.floor_area_sqm if listing.floor_area_sqm is not None else '不明'}"
    )
    if not any((listing.layout, listing.parking_slots is not None,
                listing.land_area_sqm is not None,
                listing.floor_area_sqm is not None)):
        raise SystemExit("PDFから4項目を1つも読み取れませんでした")
    print("判定: OK")


if __name__ == "__main__":
    main()
