"""実地検証: さつま町の一覧1回と、300万円以下のPDF1件だけを読む。

本番DB・Gmailには触れない。BaseScraperの10秒間隔とrobots.txt確認を通し、
PDFから駐車台数・間取り・土地面積・建物面積のどれかを読めるか確認する。
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.satsuma_bank import (  # noqa: E402
    SatsumaBankScraper,
    _extract_pdf_text,
    parse_pdf_details,
)


def show_keyword_windows(text: str) -> None:
    """読み取り失敗時だけ、個人の連絡先を除いた周辺文字を診断表示する。"""
    compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
    windows: list[str] = []
    for keyword in ("間取", "駐車", "車庫", "土地", "敷地", "建物", "床面積"):
        pos = compact.find(keyword)
        if pos >= 0:
            sample = compact[max(0, pos - 15):pos + 55]
            sample = re.sub(r"\d{2,4}-\d{2,4}-\d{3,4}", "[電話番号]", sample)
            windows.append(f"{keyword}: {sample}")
    print("診断用の項目周辺文字:")
    for window in dict.fromkeys(windows):
        print(f"  {window}")


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
    listing = candidates[0]
    response = scraper.get(listing.url)
    pdf_text = _extract_pdf_text(response.content)
    listing = scraper.apply_enrichment(listing, parse_pdf_details(pdf_text))
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
        show_keyword_windows(pdf_text)
        raise SystemExit("PDFから4項目を1つも読み取れませんでした")
    if not all((listing.layout, listing.parking_slots is not None,
                listing.floor_area_sqm is not None)):
        show_keyword_windows(pdf_text)
    print("判定: OK")


if __name__ == "__main__":
    main()
