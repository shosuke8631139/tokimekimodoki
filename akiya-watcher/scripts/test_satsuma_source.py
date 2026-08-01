"""さつま町 空き家情報バンク(売買)の接続テスト。

本番と同じ SatsumaBankScraper で実ページを取得・解析し、
読み取れた物件を一覧表示する。DB・通知は使わない読み取り専用テスト。
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
    print(f"読み取り成功: {len(listings)}件")
    for l in listings:
        price = f"{l.price_yen:,}円" if l.price_yen is not None else "価格不明"
        prev = (f" (旧{l.advertised_previous_price_yen:,}円)"
                if l.advertised_previous_price_yen else "")
        print(f"  [{l.listing_id}] {price}{prev} {l.address}")
        print(f"      {l.title}")
        print(f"      {l.url}")
    ok = len(listings) >= 5 and all(l.address.startswith("鹿児島県薩摩郡さつま町") for l in listings)
    print("判定:", "OK" if ok else "NG (構造が変わった可能性)")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
