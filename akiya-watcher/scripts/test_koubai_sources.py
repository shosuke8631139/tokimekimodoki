"""公売・県有財産の新3ソースの接続テスト。

本番と同じアダプタで実ページを取得・解析し、読み取れた物件を一覧表示する。
DB・通知は使わない読み取り専用テスト。

判定基準:
  - 国税庁: 物件が1件以上読める (現在全国75件規模)
  - KSI: 取得が通り、カード解析が動く (ラウンド間は本番設定では0件になる
    ため、テストでは include_closed=True で終了物件も解析して検証する)
  - 県有財産: 物件明細が1件以上読める
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.ksi_auction import KsiAuctionScraper  # noqa: E402
from akiya_watcher.scrapers.nta_koubai import NtaKoubaiScraper  # noqa: E402
from akiya_watcher.scrapers.pref_kagoshima_sale import (  # noqa: E402
    PrefKagoshimaSaleScraper,
)

TARGET_HINTS = ("鹿児島", "宮崎", "熊本")  # 近場の出物の目視確認用


def show(listings, limit=40) -> None:
    for ls in listings[:limit]:
        price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格不明"
        near = " ◀◀ 近場!" if any(h in f"{ls.title}{ls.address}"
                                  for h in TARGET_HINTS) else ""
        print(f"  [{ls.listing_id}] {price} {ls.address[:40]}{near}")
        print(f"      {ls.title[:70]}")
        print(f"      {ls.url}")


def main() -> None:
    ok = True

    print("===== 国税庁 公売情報 (全国) =====")
    nta = NtaKoubaiScraper({"id": "nta_koubai", "pages": 3})
    nta_items = nta.fetch_listings()
    print(f"読み取り成功: {len(nta_items)}件")
    show(nta_items)
    with_price = sum(1 for ls in nta_items if ls.price_yen is not None)
    with_addr = sum(1 for ls in nta_items if ls.address)
    print(f"価格が読めた: {with_price}件 / 住所が読めた: {with_addr}件")
    if len(nta_items) < 1:
        ok = False
        print("NG: 国税庁の物件が読めていない (構造が変わった可能性)")

    print("\n===== KSI官公庁オークション 不動産 =====")
    ksi = KsiAuctionScraper({"id": "ksi_auction", "include_closed": True})
    ksi_items = ksi.fetch_listings()
    print(f"読み取り成功: {len(ksi_items)}件 (入札終了も含めた解析検証)")
    show(ksi_items, limit=15)
    ksi_open = [ls for ls in ksi_items
                if ls.raw.get("status") not in ("入札終了", "受付終了")]
    print(f"うち入札受付中/予定: {len(ksi_open)}件 "
          "(0件ならラウンド間。新ラウンド開始で増える)")
    with_price = sum(1 for ls in ksi_items if ls.price_yen is not None)
    print(f"価格が読めた: {with_price}件 / {len(ksi_items)}件")
    if len(ksi_items) < 10 or with_price < len(ksi_items) * 0.7:
        ok = False
        print("NG: KSIのカード解析が崩れている (構造が変わった可能性)")

    print("\n===== 鹿児島県 県有財産売却 =====")
    pref = PrefKagoshimaSaleScraper({"id": "kagoshima_pref_sale"})
    pref_items = pref.fetch_listings()
    print(f"読み取り成功: {len(pref_items)}件")
    show(pref_items)
    if len(pref_items) < 1:
        ok = False
        print("NG: 県有財産の物件明細が読めていない (構造が変わった可能性)")

    print("\n判定:", "OK" if ok else "NG")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
