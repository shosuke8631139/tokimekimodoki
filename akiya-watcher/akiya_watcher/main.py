"""エントリポイント。

運用モデル: 「何もない日は何も来ない」。
  - 数時間おきの巡回 (通常実行): 値下げ・高スコア新着があった時だけ通知が鳴る
  - 週1回のダイジェスト (--digest): 通知から漏れた掘り出し候補と指値候補をまとめて送る
  - 台帳レポート (--report): 全物件をスコア順に残すHTML。通知が来た時に開く

使い方:
    python -m akiya_watcher.main --config config.yaml --report data/report.html
    python -m akiya_watcher.main --config config.yaml --digest --report data/report.html
    python -m akiya_watcher.main --config config.yaml --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .alerts import decide, offer_candidate_reason
from .criteria import Scorer
from .models import ListingContext, Score
from .notify import Notifier
from .report import render_report
from .scrapers import build_scraper
from .storage import Diff, Store


def collect(config: dict, dry_run: bool = False) -> list[tuple[Diff, Score]]:
    """全ソースから収集し、(Diff, Score) のリストを返す。"""
    scorer = Scorer(config.get("criteria", {}))
    store = None if dry_run else Store(config.get("db_path", "data/listings.db"))

    items: list[tuple[Diff, Score]] = []
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


def build_digest(items: list[tuple[Diff, Score]], offer_min_age_days: int) -> str:
    """週次ダイジェスト: 上位物件と指値候補のまとめ。"""
    ranked = sorted(items, key=lambda x: x[1].total, reverse=True)
    lines = [f"📊 週次ダイジェスト (監視 {len(items)}件)", ""]

    offers = [(d, s, offer_candidate_reason(d, offer_min_age_days))
              for d, s in ranked]
    offers = [(d, s, r) for d, s, r in offers if r]
    lines.append(f"🎯 指値候補 {len(offers)}件 — 待たずに攻める:")
    for d, s, r in offers[:5]:
        price = f"{d.listing.price_yen:,}円" if d.listing.price_yen else "価格応談"
        lines.append(f"  ・{d.listing.title} {price} ({r}) {d.listing.url}")
    lines.append("")

    lines.append("🏆 スコア上位:")
    for d, s in ranked[:5]:
        price = f"{d.listing.price_yen:,}円" if d.listing.price_yen else "価格応談"
        lines.append(f"  ・{s.total}点 {d.listing.title} {price} {d.listing.url}")
    return "\n".join(lines)


def run(config_path: str, dry_run: bool = False, report_path: str | None = None,
        digest: bool = False) -> int:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    notify_cfg = config.get("notify", {})
    min_score = notify_cfg.get("min_score", 8)
    ruin_extra = notify_cfg.get("ruin_extra_score", 5)
    offer_age = config.get("offer_list", {}).get("min_age_days", 90)

    items = collect(config, dry_run=dry_run)
    notifier = Notifier(config.get("slack_webhook_url"))

    notified = suppressed = 0
    if digest:
        if not dry_run:
            notifier.send_text(build_digest(items, offer_age))
            notified = 1
    else:
        # 通常巡回: 通知ゲートを通った物件だけ即時通知 (沈黙デフォルト)
        for diff, score in items:
            d = decide(diff, score, min_score=min_score, ruin_extra=ruin_extra)
            if d.notify and not dry_run:
                notifier.send(diff, score)
                notified += 1
            elif d.kind == "silent" and diff.kind in ("new", "changed"):
                suppressed += 1
                print(f"[silent] {diff.listing.title}: {d.reason}")

    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(
            render_report(items, offer_min_age_days=offer_age), encoding="utf-8")
        print(f"[info] 台帳レポート生成: {report_path}")

    print(f"[info] 監視 {len(items)}件 / 通知 {notified}件 / 抑制 {suppressed}件")
    if dry_run:
        for diff, score in sorted(items, key=lambda x: x[1].total, reverse=True):
            print(f"  {score.total:3d}点  {diff.listing.title}  {' '.join(score.badges)}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="鹿児島お宝再生物件ウォッチャー")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--report", help="台帳レポートHTMLの出力先パス")
    ap.add_argument("--digest", action="store_true",
                    help="即時通知の代わりに週次ダイジェストを送る")
    ap.add_argument("--dry-run", action="store_true",
                    help="DB更新・通知をせずスコア順位を表示する")
    args = ap.parse_args()
    sys.exit(run(args.config, dry_run=args.dry_run, report_path=args.report,
                 digest=args.digest))


if __name__ == "__main__":
    main()
