"""商談ノート — あなたの動きを記録して「通る指値」を学ぶ。

使い方 (Windowsは windows/deals.bat をダブルクリック):
    python -m akiya_watcher.deals --config config.yaml

番号を選んで状態を付けるだけの対話式。記録は listings.db に貯まり、
台帳レポートに「🤝商談中」バッジと実戦データとして表示される。
"""
from __future__ import annotations

import argparse
import sys

from .criteria import parse_price_yen
from .main import load_config
from .storage import DEAL_STATUSES, Store


def _fmt_price(p: int | None) -> str:
    if p is None:
        return "価格不明"
    return "0円" if p == 0 else f"{p / 10_000:,.0f}万円"


def show_history(store: Store) -> None:
    hist = store.deal_history()
    if not hist:
        print("まだ記録がありません。")
        return
    print("\n===== 実戦データ (新しい順) =====")
    for h in hist[:20]:
        offer = f" 指値{_fmt_price(h['offer_yen'])}" if h["offer_yen"] else ""
        note = f" — {h['note']}" if h["note"] else ""
        print(f"  [{h['status']}]{offer} {h['title'][:40]}{note}")


def interactive(store: Store) -> None:
    listings = store.recent_listings()
    if not listings:
        print("まだ物件データがありません。先に巡回(run_once)を実行してください。")
        return
    deals = store.deals()

    print("===== 商談ノート =====")
    print("掲載中の物件 (新しい順):\n")
    for i, ls in enumerate(listings, 1):
        mark = f" ◀ {deals[ls['uid']]['status']}" if ls["uid"] in deals else ""
        print(f"  {i:2d}. {_fmt_price(ls['price_yen']):>8}  {ls['title'][:45]}{mark}")

    print("\n記録したい物件の番号を入れてEnter (h=履歴を見る / そのままEnter=終了)")
    while True:
        raw = input("番号> ").strip()
        if not raw:
            print("保存して終了します。")
            return
        if raw.lower() == "h":
            show_history(store)
            continue
        if not raw.isdigit() or not (1 <= int(raw) <= len(listings)):
            print(f"1〜{len(listings)}の番号を入れてください。")
            continue
        ls = listings[int(raw) - 1]
        print(f"\n▼ {ls['title'][:50]} ({_fmt_price(ls['price_yen'])})")
        for i, st in enumerate(DEAL_STATUSES, 1):
            print(f"  {i}. {st}")
        st_raw = input("状態の番号> ").strip()
        if not st_raw.isdigit() or not (1 <= int(st_raw) <= len(DEAL_STATUSES)):
            print("キャンセルしました。")
            continue
        status = DEAL_STATUSES[int(st_raw) - 1]

        offer = None
        if status in ("指値中", "成約", "見送り"):
            o_raw = input("指値・成約の金額 (例: 130万 / 空欄でスキップ)> ").strip()
            if o_raw:
                offer = parse_price_yen(o_raw)
        note = input("ひとことメモ (例: 断られた・売主は遠方 / 空欄可)> ").strip()

        store.set_deal(ls["uid"], status, offer_yen=offer, note=note)
        offer_s = f" 金額{_fmt_price(offer)}" if offer else ""
        print(f"✅ 記録しました: [{status}]{offer_s}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="商談ノート")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--history", action="store_true", help="実戦データを表示して終了")
    args = ap.parse_args()
    config = load_config(args.config)
    store = Store(config.get("db_path", "data/listings.db"))
    try:
        if args.history:
            show_history(store)
        else:
            interactive(store)
    except (KeyboardInterrupt, EOFError):
        print("\n終了します。")
    finally:
        store.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
