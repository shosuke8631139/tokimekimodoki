"""エントリポイント。

使い方:
    python -m akiya_watcher.main --config config.yaml                    # 収集+通知
    python -m akiya_watcher.main --config config.yaml --report out.html  # +朝レポート生成
    python -m akiya_watcher.main --config config.yaml --dry-run          # DB更新なしで確認

定期実行は cron に登録する (README 参照)。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .criteria import Scorer
from .models import ListingContext
from .notify import Notifier
from .report import render_report
from .scrapers import build_scraper
from .storage import Diff, Store


def collect(config: dict, dry_run: bool = False) -> list[tuple[Diff, "object"]]:
    """全ソースから収集し、(Diff, Score) のリストを返す。"""
    scorer = Scorer(config.get("criteria", {}))
    store = None if dry_run else Store(config.get("db_path", "data/listings.db"))

    items = []
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
            if store:
                diff = store.upsert(ls)
            else:
                ctx = ListingContext(is_new=True, current_price_yen=ls.price_yen)
                diff = Diff(kind="new", listing=ls, context=ctx)
            items.append((diff, scorer.score(ls, diff.context)))

    if store:
        store.close()
    return items


def run(config_path: str, dry_run: bool = False, report_path: str | None = None,
        notify_min_score: int | None = None) -> int:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    items = collect(config, dry_run=dry_run)

    # 即時通知: 新着と変更のみ (毎回全件は送らない)。閾値は低め = 落としすぎない。
    min_score = notify_min_score if notify_min_score is not None \
        else config.get("notify_min_score", 5)
    notifier = Notifier(config.get("slack_webhook_url"))
    notified = 0
    for diff, score in items:
        if diff.kind in ("new", "changed") and score.total >= min_score and not dry_run:
            notifier.send(diff, score)
            notified += 1

    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(render_report(items), encoding="utf-8")
        print(f"[info] レポート生成: {report_path}")

    print(f"[info] 監視 {len(items)}件 / 通知 {notified}件")
    if dry_run:
        for diff, score in sorted(items, key=lambda x: x[1].total, reverse=True):
            print(f"  {score.total:3d}点  {diff.listing.title}  {' '.join(score.badges)}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="鹿児島お宝再生物件ウォッチャー")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--report", help="朝レポートHTMLの出力先パス")
    ap.add_argument("--dry-run", action="store_true",
                    help="DB更新・通知をせずスコア順位を表示する")
    args = ap.parse_args()
    sys.exit(run(args.config, dry_run=args.dry_run, report_path=args.report))


if __name__ == "__main__":
    main()
