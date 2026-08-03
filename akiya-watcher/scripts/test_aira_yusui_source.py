"""実地検証: 薩摩川内CGI・日置バンクの新アダプタを実サイトに当てる (2026-08-03)。

偵察(第1・2弾)で確認した構造を元に実装した2アダプタが、
本物のHTMLから正しく (件数・価格・住所・値下げ) を読めるかの最終確認。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.hioki_bank import HiokiBankScraper  # noqa: E402
from akiya_watcher.scrapers.satsumasendai_city import (  # noqa: E402
    SatsumasendaiCityScraper,
)


def show(name: str, listings) -> None:
    print(f"\n===== {name}: {len(listings)}件 =====")
    for ls in listings:
        price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格?"
        prev = (f" (前 {ls.advertised_previous_price_yen:,}円)"
                if ls.advertised_previous_price_yen else "")
        print(f"  {ls.title}  {price}{prev}")
        print(f"    住所={ls.address}  url={ls.url}")
        print(f"    説明冒頭: {ls.description[:70]}")


def main() -> None:
    sendai = SatsumasendaiCityScraper({
        "id": "satsumasendai_city_bank",
        "list_url": "https://www.city.satsumasendai.lg.jp/cgi-bin/recruit.php/3/list",
    })
    show("薩摩川内CGI", sendai.fetch_listings())

    hioki = HiokiBankScraper({
        "id": "hioki_akiya_bank",
        "list_urls": [
            "https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/akiyabank/akiyabank_higashiichiki.html",
            "https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/akiyabank/akiyabank_ijuin.html",
            "https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/akiyabank/akiyabank_hiyoshi.html",
            "https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/akiyabank/akiyabank_fukiage.html",
        ],
    })
    show("日置バンク(4地域)", hioki.fetch_listings())


if __name__ == "__main__":
    main()
