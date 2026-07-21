"""エントリポイント。

使い方:
    python -m akiya_watcher.main --config config.yaml           # 1回実行
    python -m akiya_watcher.main --config config.yaml --dry-run # DB更新せず判定だけ表示

定期実行は cron に登録する (README 参照)。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .criteria import Judge
from .notify import Notifier, format_message
from .scrapers import build_scraper
from .storage import Diff, Store


def run(config_path: str, dry_run: bool = False) -> int:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    judge = Judge(config.get("criteria", {}))
    notifier = Notifier(config.get("slack_webhook_url"))
    store = None if dry_run else Store(config.get("db_path", "data/listings.db"))

    total_hits = 0
    for source_cfg in config.get("sources", []):
        if not source_cfg.get("enabled", True):
            continue
        try:
            scraper = build_scraper(source_cfg)
            listings = scraper.fetch_listings()
        except Exception as e:
            print(f"[error] {source_cfg.get('id')}: 取得失敗 - {e}", file=sys.stderr)
            continue
        print(f"[info] {source_cfg.get('id')}: {len(listings)}件取得")

        for ls in listings:
            judgement = judge.judge(ls)
            if not judgement.matched:
                continue
            total_hits += 1
            if dry_run:
                print(format_message(Diff(kind="new", listing=ls), judgement))
                print("-" * 40)
                continue
            diff = store.upsert(ls)
            if diff is not None:
                notifier.send(diff, judgement)

    if store:
        store.close()
    print(f"[info] 条件合致: {total_hits}件")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="鹿児島お宝再生物件ウォッチャー")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--dry-run", action="store_true",
                    help="DB更新・通知をせず判定結果を表示する")
    args = ap.parse_args()
    sys.exit(run(args.config, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
