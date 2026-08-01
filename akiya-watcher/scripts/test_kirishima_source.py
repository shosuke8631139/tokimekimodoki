"""霧島市 空き家バンクの接続テスト。

1. 案内ページから地区別一覧ページのURLを自動発見して表示
   (config.yaml に貼るためのリスト)
2. 本番と同じ KirishimaBankScraper で全地区を取得・解析して一覧表示
読み取り専用テスト。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.kirishima_bank import KirishimaBankScraper  # noqa: E402

HUB = "https://www.city-kirishima.jp/kyodo/shise/ijuteju/akiya/akiyabankriyoukibounokata.html"


def main() -> None:
    res = requests.get(HUB, timeout=30,
                       headers={"User-Agent": "akiya-watcher/0.1 (connection test)"})
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")
    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if re.search(r"空き家バンク一覧（.+地区）", text):
            url = urljoin(HUB, a["href"])
            if url not in urls:
                urls.append(url)
    print(f"発見した地区ページ: {len(urls)}件 (config.yaml 用)")
    for u in urls:
        print(f'      - "{u}"')

    scraper = KirishimaBankScraper({"id": "kirishima_akiya_bank", "list_urls": urls})
    listings = scraper.fetch_listings()
    print(f"読み取り成功: 売買 {len(listings)}件")
    for l in listings:
        price = f"{l.price_yen:,}円" if l.price_yen is not None else "価格不明"
        print(f"  [{l.listing_id}] {price} {l.address}")
        print(f"      {l.url}")
    ok = len(urls) >= 5 and all(l.address.startswith("鹿児島県霧島市") for l in listings)
    print("判定:", "OK" if ok else "NG (構造が変わった可能性)")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
