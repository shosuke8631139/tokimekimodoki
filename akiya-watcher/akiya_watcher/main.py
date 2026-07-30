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
from .criteria import Scorer, is_keep
from .kanpo import digest_lines as kanpo_digest_lines
from .models import ListingContext, Score
from .notify import Notifier
from .report import render_report
from .scrapers import build_scraper
from .storage import Diff, Store


class ConfigError(Exception):
    """設定ファイルの問題。日本語の説明メッセージを持つ。"""


def load_config(config_path: str) -> dict:
    """config.yaml を読み、間違いがあれば日本語で説明して止まる。"""
    p = Path(config_path)
    if not p.exists():
        raise ConfigError(f"設定ファイルが見つかりません: {p}\n"
                          "config.yaml と同じ場所で実行しているか確認してください。")
    try:
        config = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = f"(だいたい {mark.line + 1} 行目)" if mark else ""
        raise ConfigError(
            f"設定ファイルの書き方に間違いがあります {line}。\n"
            "よくある原因: 行頭の空白の数がずれている / コロン(:)の後の空白がない。\n"
            "直し方が分からなければ、そのままの内容を相談してください。") from e
    if not isinstance(config, dict):
        raise ConfigError("設定ファイルが空、または形式が違います。")
    return config


def collect(config: dict, dry_run: bool = False,
            ) -> tuple[list[tuple[Diff, Score]], list[dict]]:
    """全ソースから収集し、((Diff, Score) のリスト, 掲載終了リスト) を返す。"""
    criteria = config.get("criteria", {})
    scorer = Scorer(criteria)
    # リサーチ範囲: 指定があれば範囲外の市町村は収集しない。
    # 住所が読み取れない物件は落としすぎ防止のため残す。
    target_areas = criteria.get("target_areas", [])
    # 価格の足切り (2026-07 ユーザー判断: 高額物件と「応相談」は時間の無駄なので外す)
    max_price = criteria.get("max_price_yen")
    include_unknown_price = criteria.get("include_price_unknown", True)
    store = None if dry_run else Store(config.get("db_path", "data/listings.db"))

    items: list[tuple[Diff, Score]] = []
    gone_uids: list[str] = []
    out_of_area = over_price = unknown_price = 0
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

        seen_uids: set[str] = set()
        pinned = getattr(scraper, "always_keep", False)
        for ls in listings:
            # 足切りで除外しても「サイトにはまだ掲載されている」ので、
            # 掲載終了(売れた)と誤記録しないよう seen には数えておく
            # (指名追跡物件 pinned は本人の意思が最優先なので足切り免除)
            if (not pinned and target_areas and ls.address
                    and not any(area in ls.address for area in target_areas)):
                out_of_area += 1
                seen_uids.add(ls.uid)
                continue
            # 「応相談カット」は価格欄が明確なソースのみ。メール型の価格Noneは
            # 読み取り失敗の可能性が高いので、要確認として台帳に残す
            if (ls.price_yen is None and not include_unknown_price
                    and scraper.prices_reliable and not pinned):
                unknown_price += 1
                seen_uids.add(ls.uid)
                continue
            if (max_price and ls.price_yen and ls.price_yen > max_price
                    and not pinned):
                over_price += 1
                seen_uids.add(ls.uid)
                continue
            if store:
                diff = store.upsert(ls)
                seen_uids.add(ls.uid)
            else:
                ctx = ListingContext(is_new=True, current_price_yen=ls.price_yen)
                diff = Diff(kind="new", listing=ls, context=ctx)
            # 掲載側が変更前価格を明示している場合(Sumai空き家の「300万→100万」等)、
            # こちらの履歴が無くても値下げとして扱う
            if (ls.advertised_previous_price_yen
                    and diff.context.previous_price_yen is None):
                diff.context.previous_price_yen = ls.advertised_previous_price_yen
                if diff.kind == "new":
                    diff.context.price_changed = True
            score = scorer.score(ls, diff.context)
            if store:
                store.set_keep(ls.uid, True if pinned else is_keep(score))
            items.append((diff, score))

        # 一覧型ソースのみ: 今回見えなかった物件を掲載終了(売れた?)として記録
        if store and scraper.full_snapshot and listings:
            gone = store.finalize_crawl(source_cfg["id"], seen_uids)
            if gone:
                print(f"[info] {source_cfg['id']}: 掲載終了 {len(gone)}件")
                gone_uids.extend(gone)

    delisted = store.recent_delisted(within_days=30) if store else []
    deals = store.deals() if store else {}
    deal_history = store.deal_history() if store else []
    # ⭐キープ物件が今回掲載終了した場合は特別に知らせる (売れた可能性が高い)
    keep_gone = []
    if store:
        for uid in gone_uids:
            info = store.listing_info(uid)
            if info and info["is_keep"]:
                keep_gone.append(info)
        store.close()
    if out_of_area:
        print(f"[info] リサーチ範囲外のためスキップ: {out_of_area}件")
    if over_price:
        print(f"[info] 価格上限({max_price:,}円)超のためスキップ: {over_price}件")
    if unknown_price:
        print(f"[info] 価格応相談のためスキップ: {unknown_price}件")
    return items, delisted, deals, deal_history, keep_gone


def build_digest(items: list[tuple[Diff, Score]], offer_min_age_days: int,
                 kanpo_enabled: bool = True) -> str:
    """週次ダイジェスト: 上位物件と指値候補のまとめ + 官報チェック便。"""
    ranked = sorted(items, key=lambda x: x[1].total, reverse=True)
    lines = [f"📊 週次ダイジェスト (監視 {len(items)}件)", ""]

    offers = [(d, s, offer_candidate_reason(d, offer_min_age_days))
              for d, s in ranked]
    offers = [(d, s, r) for d, s, r in offers if r]
    lines.append(f"🎯 指値候補 {len(offers)}件 — 待たずに攻める:")
    for d, s, r in offers[:5]:
        price = (f"{d.listing.price_yen:,}円" if d.listing.price_yen is not None
                 else "価格応談")
        lines.append(f"・{d.listing.title} {price} ({r})")
        lines.append(f"  {d.listing.url}")
    lines.append("")

    lines.append("🏆 評価上位 (10点満点):")
    for d, s in ranked[:5]:
        price = (f"{d.listing.price_yen:,}円" if d.listing.price_yen is not None
                 else "価格応談")
        badges = " ".join(s.badges) or "情報少・要確認"
        lines.append(f"・{s.out_of_ten}/10点 {d.listing.title} {price}")
        lines.append(f"  [{badges}]")
        lines.append(f"  {d.listing.url}")
    lines.append("")
    if kanpo_enabled:
        lines.extend(kanpo_digest_lines())
        lines.append("")
    lines.append("※ 点数の内訳は添付レポートの「スコア内訳」で確認できます。")
    return "\n".join(lines)


def build_heartbeat(items: list[tuple[Diff, Score]], top_n: int = 5,
                    kanpo_enabled: bool = True, notified: int = 0) -> str:
    """毎日の定期便: 1日1回必ず送る「官報チェック+注目上位」。

    通知が出た日も送る (2026-07-31 修正: 以前は通知が出ると官報コーナーごと
    消えてしまい「官報情報がメールに載っていない」状態になっていた)。
    """
    ranked = sorted(items, key=lambda x: x[1].total, reverse=True)
    if notified > 0:
        lines = [f"📮 本日の定期便 — 物件の動き{notified}件は別メールでお知らせ済み", ""]
    else:
        lines = ["📮 本日の定期便 — 今回は通知に値する動きなし", ""]
    if kanpo_enabled:
        import datetime
        from .kanpo import daily_lines
        lines += daily_lines(datetime.date.fromisoformat(jst_today()))
        lines.append("")
    if ranked:
        lines.append(f"監視中 {len(items)}件。いま熱い物件 上位{min(top_n, len(ranked))}件:")
        for d, s in ranked[:top_n]:
            price = (f"{d.listing.price_yen:,}円" if d.listing.price_yen is not None
                     else "価格応談")
            badges = " ".join(s.badges) or "情報少・要確認"
            lines.append(f"・{s.out_of_ten}/10点 {d.listing.title} {price}")
            lines.append(f"  [{badges}]")
            lines.append(f"  {d.listing.url}")
    else:
        lines.append("監視中の物件が0件です (情報源の取得失敗が続く場合は要確認)。")
    lines.append("")
    lines.append("※ この定期便は1日1回。値下げ・高スコア新着・キープ物件の変化は、")
    lines.append("   これとは別にその都度すぐ鳴ります。")
    return "\n".join(lines)


def jst_today() -> str:
    """日本時間での今日の日付 (YYYY-MM-DD)。生存報告の1日1回判定に使う。"""
    import datetime
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(jst).date().isoformat()


def self_check(config_path: str) -> int:
    """設定の健康診断。何が出来ていて何が足りないかを日本語で報告する。"""
    import os
    ok = True

    def good(msg): print(f"  ✅ {msg}")

    def bad(msg):
        nonlocal ok
        ok = False
        print(f"  ❌ {msg}")

    print("===== 設定の健康診断 =====")
    try:
        config = load_config(config_path)
        good("設定ファイルは正しく読めます")
    except ConfigError as e:
        print(f"  ❌ {e}")
        print("===== 診断結果: 設定ファイルを直してください =====")
        return 1

    areas = config.get("criteria", {}).get("target_areas", [])
    if areas:
        good(f"リサーチ範囲: {len(areas)}市町村 (例: {'、'.join(areas[:3])} …)")
    else:
        print("  ⚠️ リサーチ範囲が未設定 (全地域が対象になります)")

    enabled = [s for s in config.get("sources", []) if s.get("enabled", True)]
    if enabled:
        good("監視する情報源: " + "、".join(s.get("id", "?") for s in enabled))
    else:
        bad("有効な情報源がひとつもありません (sources の enabled を確認)")

    for s in enabled:
        if s.get("type") != "gmail_imap":
            continue
        user = s.get("username") or os.environ.get(
            s.get("username_env", "GMAIL_USERNAME"), "")
        if not user or "your-address" in user:
            bad(f"[{s.get('id')}] Gmailアドレスが未設定です "
                "(環境変数 GMAIL_USERNAME、または config.yaml の username)")
            continue
        good(f"[{s.get('id')}] Gmailアドレス: {user}")
        env = s.get("password_env", "GMAIL_APP_PASSWORD")
        if os.environ.get(env):
            good("アプリパスワードは設定済み")
        else:
            bad(f"アプリパスワードが未設定です (環境変数 {env}。"
                "windows/set_gmail_password.bat で設定できます)")

    email = config.get("notify", {}).get("email")
    email_user = ""
    if email is not None:
        email_user = email.get("username") or os.environ.get(
            email.get("username_env", "GMAIL_USERNAME"), "")
    if email_user and "your-address" not in email_user:
        good(f"通知メールの宛先: {email_user}")
        if not os.environ.get(email.get("password_env", "GMAIL_APP_PASSWORD")):
            bad("通知メール用のアプリパスワードが未設定です")
    elif os.environ.get("SLACK_WEBHOOK_URL") or config.get("slack_webhook_url"):
        good("通知先: Slack")
    else:
        print("  ⚠️ 通知先が未設定 (当面は画面とレポートだけで動きます)")

    print("===== 診断結果: " + ("すべてOKです!" if ok else "❌の項目を直してください")
          + " =====")
    return 0 if ok else 1


def run(config_path: str, dry_run: bool = False, report_path: str | None = None,
        digest: bool = False) -> int:
    config = load_config(config_path)
    notify_cfg = config.get("notify", {})
    min_score = notify_cfg.get("min_score", 8)
    ruin_extra = notify_cfg.get("ruin_extra_score", 5)
    offer_age = config.get("offer_list", {}).get("min_age_days", 90)

    items, delisted, deals, deal_history, keep_gone = collect(config, dry_run=dry_run)
    notifier = Notifier(config.get("slack_webhook_url"),
                        email=notify_cfg.get("email"))

    # レポートは通知より先に生成する (ダイジェストに添付するため)
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(
            render_report(items, offer_min_age_days=offer_age, delisted=delisted,
                          deals=deals, deal_history=deal_history),
            encoding="utf-8")
        print(f"[info] 台帳レポート生成: {report_path}")

    notified = suppressed = 0
    if digest:
        if not dry_run:
            kanpo_on = config.get("kanpo", {}).get("enabled", True)
            notifier.send_text(build_digest(items, offer_age,
                                            kanpo_enabled=kanpo_on),
                               attachment=report_path)
            notified = 1
            # ダイジェスト自体がメールなので、同日の生存報告は不要と記録する
            meta_store = Store(config.get("db_path", "data/listings.db"))
            meta_store.set_meta("last_mail_date", jst_today())
            meta_store.close()
    else:
        # 通常巡回: 通知ゲートを通った物件だけ即時通知 (沈黙デフォルト)
        for diff, score in items:
            d = decide(diff, score, min_score=min_score, ruin_extra=ruin_extra)
            # 指名追跡物件 (source="watch") はスコアに関わらずキープ扱い
            keep = is_keep(score) or diff.listing.source == "watch"
            # ⭐キープ物件は通常なら沈黙する「記載変更」でも知らせる
            if not d.notify and keep and diff.kind == "changed":
                d = type(d)(True, "keep", "⭐キープ物件に変化あり")
            if d.notify and not dry_run:
                notifier.send(diff, score)
                notified += 1
            elif d.kind == "silent" and diff.kind in ("new", "changed"):
                suppressed += 1
                print(f"[silent] {diff.listing.title}: {d.reason}")

        # ⭐キープ物件の掲載終了 = 売れた可能性大。逃した事実も速報する
        for info in keep_gone:
            if not dry_run:
                price = (f"{info['price_yen']:,}円" if info["price_yen"] is not None
                         else "価格不明")
                notifier.send_text(
                    f"⭐ キープ物件が掲載終了(売れた可能性)\n"
                    f"物件名: {info['title']}\n価格: {price}\nURL: {info['url']}")
                notified += 1

        # 毎日の定期便: 通知の有無に関係なく1日1回必ず送る (2026-07-31 修正)。
        # 官報チェックと注目上位を毎日届けるのが目的。送った日は meta に記録し、
        # 同日の以降の巡回では沈黙する (日曜はダイジェストが定期便を兼ねる)。
        if not dry_run and notify_cfg.get("heartbeat", True):
            meta_store = Store(config.get("db_path", "data/listings.db"))
            today = jst_today()
            if meta_store.get_meta("last_mail_date") != today:
                kanpo_on = config.get("kanpo", {}).get("enabled", True)
                notifier.send_text(build_heartbeat(items, kanpo_enabled=kanpo_on,
                                                   notified=notified),
                                   attachment=report_path)
                meta_store.set_meta("last_mail_date", today)
                print("[info] 定期便を送信 (本日初回)")
            meta_store.close()

    # 通知が出た巡回では、レポート本体もメール添付で届ける
    # (スマホのGmailから添付を開けばブラウザで見られる)
    if report_path and not digest:
        attach = notify_cfg.get("email", {}).get("attach_report", True) \
            if notify_cfg.get("email") is not None else False
        if attach and not dry_run and (notified > 0):
            notifier.send_report(
                report_path,
                note=("通知した物件の全体像はこのレポートで確認できます。"
                      "添付の report.html を開いてください。"))

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
    ap.add_argument("--check", action="store_true",
                    help="設定の健康診断 (何が足りないかを日本語で表示)")
    ap.add_argument("--dry-run", action="store_true",
                    help="DB更新・通知をせずスコア順位を表示する")
    args = ap.parse_args()
    if args.check:
        sys.exit(self_check(args.config))
    try:
        sys.exit(run(args.config, dry_run=args.dry_run, report_path=args.report,
                     digest=args.digest))
    except ConfigError as e:
        print(f"[設定エラー] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
