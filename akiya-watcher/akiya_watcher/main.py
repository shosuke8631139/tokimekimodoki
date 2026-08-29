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
import json
import sys
from pathlib import Path

import yaml

from .alerts import decide, offer_candidate_reason
from .criteria import Scorer, assess_zanchi, is_keep
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


def merge_keep_entries(sources: list[dict], keeps: list[dict]) -> int:
    """メール⭐キープ登録を追跡リスト(watch)の entries に合流させる。

    config直書きの指名物件と同じ扱いになる (毎巡回ページ直接確認・
    ⭐キープ・足切り免除)。戻り値 = 新たに合流した件数。
    """
    watch = next((s for s in sources
                  if s.get("type") == "watch" and s.get("enabled", True)), None)
    if watch is None or not keeps:
        return 0
    entries = watch.setdefault("entries", [])
    existing = {e.get("url", "").strip().rstrip("/") for e in entries}
    added = 0
    for k in keeps:
        url = k.get("url", "").strip()
        if not url or url.rstrip("/") in existing:
            continue
        note = f"⭐メールでキープ登録 {k.get('added_on', '')}".strip()
        if k.get("note"):
            note += f" — {k['note']}"
        entries.append({"url": url, "note": note})
        existing.add(url.rstrip("/"))
        added += 1
    return added


def _pull_keep_mail(config: dict, store) -> list[dict]:
    """keepメールを確認して台帳へ登録し、追跡リストに合流させる。

    戻り値 = 今回新規登録の一覧 (まとめメールでの受付報告用。
    キャッシュ消失で再読込した古い登録まで報告しないよう、メールの
    日付が confirm_within_days 以内のものだけ)。IMAP不通でも巡回は止めない。
    """
    from datetime import date, timedelta
    cfg = config.get("keep_mail", {})
    if not cfg.get("enabled") or store is None:
        return []
    try:
        from .keep_mail import fetch_keep_entries
        fetched = fetch_keep_entries(cfg)
    except Exception as e:
        print(f"[warn] keepメール確認をスキップ: {e}", file=sys.stderr)
        fetched = []
    cutoff = (date.today()
              - timedelta(days=cfg.get("confirm_within_days", 7))).isoformat()
    keep_new = []
    for e in fetched:
        if (store.upsert_keep(e["url"], e.get("note", ""), e.get("added_on", ""))
                and e.get("added_on", "") >= cutoff):
            keep_new.append(e)
    merged = merge_keep_entries(config.get("sources", []), store.keep_entries())
    if fetched or merged:
        print(f"[info] keepメール: 登録{len(fetched)}件確認 / "
              f"追跡リストへ{merged}件合流")
    return keep_new


def collect(config: dict, dry_run: bool = False) -> tuple:
    """全ソースから収集する。

    戻り値: (items=(Diff, Score)のリスト, 掲載終了, 商談状態, 商談履歴,
    ⭐キープ物件の掲載終了, ⭐メールキープの新規登録)
    """
    criteria = config.get("criteria", {})
    scorer = Scorer(criteria)
    # リサーチ範囲: 指定があれば範囲外の市町村は収集しない。
    # 住所が読み取れない物件は落としすぎ防止のため残す。
    target_areas = criteria.get("target_areas", [])
    # 価格の足切り (2026-07 ユーザー判断: 高額物件と「応相談」は時間の無駄なので外す)
    max_price = criteria.get("max_price_yen")
    include_unknown_price = criteria.get("include_price_unknown", True)
    store = None if dry_run else Store(config.get("db_path", "data/listings.db"))
    # メール1タップの⭐キープ登録を追跡リストへ合流させてから巡回する
    keep_new = _pull_keep_mail(config, store)

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
            # PDF等の詳細資料は、新着または一覧の内容・価格・URLが変わった時だけ読む。
            # 変化がなければDBの読み取り結果を戻し、毎巡回の再取得を避ける。
            enrich = getattr(scraper, "enrich_listing", None)
            apply_cached = getattr(scraper, "apply_enrichment", None)
            export = getattr(scraper, "export_enrichment", None)
            if store and all(callable(x) for x in (enrich, apply_cached, export)):
                source_hash = ls.content_hash()
                cached = store.get_listing_enrichment(
                    ls.uid, ls.url, source_hash)
                if cached is not None:
                    ls = apply_cached(ls, cached)
                else:
                    try:
                        ls = enrich(ls)
                    except Exception as e:
                        print(f"[warn] {ls.uid}: 詳細資料を読めませんでした - {e}",
                              file=sys.stderr)
                    else:
                        store.save_listing_enrichment(
                            ls.uid, ls.url, source_hash, export(ls))
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
    return items, delisted, deals, deal_history, keep_gone, keep_new


def _top_uids(items: list[tuple[Diff, Score]], n: int = 5) -> list[str]:
    """定期便の上位n件のuid。「前回も紹介した物件」の記録に使う。"""
    ranked = sorted(items, key=lambda x: x[1].total, reverse=True)
    return [d.listing.uid for d, _ in ranked[:n]]


def _car(d: Diff) -> str:
    """一覧行に添える車の所要時間 (例: ' 🚗60分○')。地名不明なら空文字。"""
    from .travel import drive_minutes, zone_label
    mins = drive_minutes(d.listing.address)
    if mins is None:
        return ""
    return f" 🚗{mins}分{zone_label(mins)[0]}"


def _keep_lines(d: Diff) -> list[str]:
    """一覧行に添える「⭐キープ」1タップ登録リンク。追跡済みには付けない。"""
    from .notify import keep_mailto_line
    if d.listing.source == "watch":
        return []
    kl = keep_mailto_line(d.listing.url)
    return [f"  {kl}"] if kl else []


def _zanchi_candidates(items: list[tuple[Diff, Score]]) -> list[tuple[Diff, Score]]:
    """残置物確定→存在明示→現状有姿のみ、の順で候補を返す。"""
    confidence = {"confirmed": 3, "present": 2, "as_is": 1}
    candidates = [
        (d, s) for d, s in items if assess_zanchi(d.listing).is_candidate
    ]
    return sorted(
        candidates,
        key=lambda x: (confidence[assess_zanchi(x[0].listing).status], x[1].total),
        reverse=True,
    )


def _zanchi_summary(items: list[tuple[Diff, Score]]) -> str:
    """日次メール用の短い残置物集計。"""
    statuses = [assess_zanchi(d.listing).status for d, _ in items]
    return ("🪑 残置物判定: "
            f"A確定 {statuses.count('confirmed')}件 / "
            f"B残置物あり {statuses.count('present')}件 / "
            f"C現状有姿のみ {statuses.count('as_is')}件 / "
            f"売主撤去・撤去済み {statuses.count('removal')}件")


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
        lines.extend(_keep_lines(d))
    lines.append("")

    zanchi = _zanchi_candidates(ranked)
    lines.append(f"🪑 残置物・現状有姿候補 {len(zanchi)}件:")
    for d, _ in zanchi[:5]:
        assessment = assess_zanchi(d.listing)
        price = (f"{d.listing.price_yen:,}円" if d.listing.price_yen is not None
                 else "価格応談")
        lines.append(f"・{assessment.label} | {d.listing.title} {price}")
        lines.append(f"  {d.listing.url}")
        lines.extend(_keep_lines(d))
    if not zanchi:
        lines.append("・現在、掲載文から拾える候補なし")
    lines.append("")

    lines.append("🏆 評価上位 (10点満点):")
    for d, s in ranked[:5]:
        price = (f"{d.listing.price_yen:,}円" if d.listing.price_yen is not None
                 else "価格応談")
        badges = " ".join(s.badges) or "情報少・要確認"
        lines.append(f"・{s.out_of_ten}/10点 {d.listing.title} {price}{_car(d)}")
        lines.append(f"  [{badges}]")
        lines.append(f"  {d.listing.url}")
        lines.extend(_keep_lines(d))
    lines.append("")
    if kanpo_enabled:
        lines.extend(kanpo_digest_lines())
        lines.append("")
    lines.append("※ 点数の内訳は添付レポートの「スコア内訳」で確認できます。")
    return "\n".join(lines)


def build_heartbeat(items: list[tuple[Diff, Score]], top_n: int = 5,
                    kanpo_enabled: bool = True, notified: int = 0,
                    bundled: bool = False,
                    prev_uids: set[str] | None = None) -> str:
    """毎日の定期便: 1日1回必ず送る「官報チェック+注目上位」。

    通知が出た日も送る (2026-07-31 修正: 以前は通知が出ると官報コーナーごと
    消えてしまい「官報情報がメールに載っていない」状態になっていた)。
    bundled=True はまとめメールに同梱される場合 (見出しだけ変える)。
    prev_uids = 前回の定期便で紹介済みの物件uid (2026-08-02 ユーザー要望
    「同じ物件を何回も送られると混乱する」対策)。🆕/（既出）を明示し、
    全員が前回と同じ顔ぶれなら一覧を畳んで1行にする。
    """
    ranked = sorted(items, key=lambda x: x[1].total, reverse=True)
    prev_uids = prev_uids or set()
    if bundled:
        lines = ["📮 本日の定期便", ""]
    elif notified > 0:
        lines = [f"📮 本日の定期便 — 物件の動き{notified}件は別メールでお知らせ済み", ""]
    else:
        lines = ["📮 本日の定期便 — 今回は通知に値する動きなし", ""]
    if kanpo_enabled:
        import datetime
        from .kanpo import daily_lines
        lines += daily_lines(datetime.date.fromisoformat(jst_today()))
        lines.append("")
    lines.append(_zanchi_summary(items))
    lines.append("詳細は添付台帳の「残置物・現状有姿候補」で確認できます。")
    lines.append("")
    if ranked:
        top = ranked[:top_n]
        all_seen = prev_uids and all(d.listing.uid in prev_uids for d, _ in top)
        if all_seen:
            # 新顔ゼロの日は畳む — 同じ一覧を毎日繰り返さない
            lines.append(f"監視中 {len(items)}件。注目上位{len(top)}件は"
                         "前回と同じ顔ぶれ(新顔なし)。詳細は添付の台帳で。")
        else:
            lines.append(f"監視中 {len(items)}件。いま熱い物件 上位{len(top)}件:")
            for d, s in top:
                price = (f"{d.listing.price_yen:,}円"
                         if d.listing.price_yen is not None else "価格応談")
                badges = " ".join(s.badges) or "情報少・要確認"
                mark = "" if not prev_uids else (
                    "（既出）" if d.listing.uid in prev_uids else "🆕 ")
                head_mark = mark if mark == "🆕 " else ""
                tail_mark = mark if mark == "（既出）" else ""
                lines.append(f"・{head_mark}{s.out_of_ten}/10点 "
                             f"{d.listing.title} {price}{_car(d)}{tail_mark}")
                lines.append(f"  [{badges}]")
                lines.append(f"  {d.listing.url}")
                lines.extend(_keep_lines(d))
    else:
        lines.append("監視中の物件が0件です (情報源の取得失敗が続く場合は要確認)。")
    lines.append("")
    lines.append("※ この定期便は1日1回。値下げ・高スコア新着・キープ物件の変化は、")
    lines.append("   これとは別にその都度すぐ鳴ります。")
    return "\n".join(lines)


def build_patrol_summary(to_send: list[tuple[Diff, Score]],
                         keep_gone_texts: list[str] | None = None,
                         heartbeat_text: str | None = None,
                         quiet_new: list[tuple[Diff, Score]] | None = None,
                         keep_added_texts: list[str] | None = None) -> str:
    """1回の巡回の通知を1通にまとめる (2026-08-01 ユーザー要望:
    「メールが一気に何件も来て見づらい」対策)。

    並び順: ⭐キープ関連 → 値下げ(下げ幅の大きい順) → その他(評価の高い順)
    → 通知基準未満の新着(1行ずつ。2026-08-02 ユーザー要望:
    「新着はどれもその都度目に入るように」)。1行目が件名になる。
    """
    from .notify import format_message
    keep_gone_texts = keep_gone_texts or []
    quiet_new = quiet_new or []
    keep_added_texts = keep_added_texts or []

    drops = [(d, s) for d, s in to_send
             if d.context.price_changed and d.context.drop_pct]
    others = [(d, s) for d, s in to_send if (d, s) not in drops]
    drops.sort(key=lambda x: x[0].context.drop_pct or 0, reverse=True)
    others.sort(key=lambda x: x[1].total, reverse=True)

    parts = []
    if keep_added_texts:
        parts.append(f"⭐キープ登録{len(keep_added_texts)}件")
    if keep_gone_texts:
        parts.append(f"⭐掲載終了{len(keep_gone_texts)}件")
    if drops:
        parts.append(f"値下げ{len(drops)}件(最大▼{drops[0][0].context.drop_pct}%)")
    news = sum(1 for d, _ in others if d.kind == "new")
    changed = len(others) - news
    if news:
        parts.append(f"新着{news}件")
    if changed:
        parts.append(f"変更{changed}件")
    if quiet_new:
        label = (f"ほか新着{len(quiet_new)}件" if parts
                 else f"新着(注目度低め){len(quiet_new)}件")
        parts.append(label)
    subject = "🏠 巡回まとめ: " + "・".join(parts)
    subject_items = to_send + quiet_new
    has_zanchi_candidate = any(
        assess_zanchi(d.listing).status in {"confirmed", "present"}
        for d, _ in subject_items
    )
    if has_zanchi_candidate:
        subject = "【残置物候補あり】" + subject
    has_ichikikushikino = any(
        d.listing.source == "ichikikushikino_akiya_bank"
        or "いちき串木野市" in d.listing.address
        for d, _ in subject_items
    )
    if has_ichikikushikino:
        subject = "【一木串木野あり】" + subject

    blocks = [subject]
    blocks.extend(keep_added_texts)
    blocks.extend(keep_gone_texts)
    blocks.extend(format_message(d, s) for d, s in drops + others)
    if quiet_new:
        qlines = ["── その他の新着(通知基準未満・詳細は添付の台帳で) ──"]
        for d, s in sorted(quiet_new, key=lambda x: x[1].total, reverse=True):
            price = (f"{d.listing.price_yen:,}円"
                     if d.listing.price_yen is not None else "価格応談")
            qlines.append(f"・{s.out_of_ten}/10 {d.listing.title} {price}{_car(d)}")
            qlines.append(f"  {d.listing.url}")
            qlines.extend(_keep_lines(d))
        blocks.append("\n".join(qlines))
    if heartbeat_text:
        blocks.append(heartbeat_text)
    return "\n\n――――――――――\n\n".join(blocks)


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

    km = config.get("keep_mail", {})
    if km.get("enabled"):
        user = km.get("username") or os.environ.get(
            km.get("username_env", "GMAIL_USERNAME"), "")
        if user:
            good(f"⭐メールキープ受付: 有効 (件名 "
                 f"'{km.get('subject_keyword', 'keep')}' を巡回ごとに確認)")
        else:
            bad("⭐メールキープ: Gmailアドレスが未設定です "
                "(環境変数 GMAIL_USERNAME)")

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
        digest: bool = False, preview_bundle: bool = False) -> int:
    config = load_config(config_path)
    notify_cfg = config.get("notify", {})
    min_score = notify_cfg.get("min_score", 8)
    ruin_extra = notify_cfg.get("ruin_extra_score", 5)
    always_notify_sources = {
        source["id"] for source in config.get("sources", [])
        if source.get("always_notify", False)
    }
    offer_age = config.get("offer_list", {}).get("min_age_days", 90)

    (items, delisted, deals, deal_history, keep_gone,
     keep_new) = collect(config, dry_run=dry_run)
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

    if preview_bundle:
        # まとめメールの見た目確認用に1通だけ送る (通知ゲート・1日1回の
        # 定期便メタは触らない。値下げ履歴のある物件を値下げ枠で見せる)
        kanpo_on = config.get("kanpo", {}).get("enabled", True)
        drops, others = [], []
        for d, s in items:
            if d.context.drop_pct:
                d.context.price_changed = True  # まとめの値下げ枠に入れる
                drops.append((d, s))
            else:
                others.append((d, s))
        others.sort(key=lambda x: x[1].total, reverse=True)
        picked = drops if drops else others[:3]
        hb = build_heartbeat(items, kanpo_enabled=kanpo_on, bundled=True)
        text = build_patrol_summary(picked, heartbeat_text=hb)
        text = text.replace("🏠 巡回まとめ:", "🏠 巡回まとめ(プレビュー):", 1)
        if not dry_run:
            notifier.send_text(text, attachment=report_path)
        print(f"[info] まとめメールのプレビューを送信 ({len(picked)}件)")
        return 0

    notified = suppressed = 0
    if digest:
        if not dry_run:
            kanpo_on = config.get("kanpo", {}).get("enabled", True)
            text = build_digest(items, offer_age, kanpo_enabled=kanpo_on)
            if keep_new:
                head = "\n".join("⭐ キープ登録を受け付けました: " + e["url"]
                                 for e in keep_new)
                text = head + "\n\n" + text
            notifier.send_text(text, attachment=report_path)
            notified = 1
            # ダイジェスト自体がメールなので、同日の生存報告は不要と記録する
            meta_store = Store(config.get("db_path", "data/listings.db"))
            meta_store.set_meta("last_mail_date", jst_today())
            meta_store.close()
    else:
        # 通常巡回: 通知ゲートを通った物件だけ即時通知 (沈黙デフォルト)
        bundle = notify_cfg.get("bundle", True)
        to_send: list[tuple[Diff, Score]] = []
        quiet_new: list[tuple[Diff, Score]] = []
        for diff, score in items:
            d = decide(
                diff, score, min_score=min_score, ruin_extra=ruin_extra,
                always_notify=diff.listing.source in always_notify_sources,
            )
            # 指名追跡物件 (source="watch") はスコアに関わらずキープ扱い
            keep = is_keep(score) or diff.listing.source == "watch"
            # ⭐キープ物件は通常なら沈黙する「記載変更」でも知らせる
            if not d.notify and keep and diff.kind == "changed":
                d = type(d)(True, "keep", "⭐キープ物件に変化あり")
            if d.notify and not dry_run:
                to_send.append((diff, score))
                notified += 1
            elif d.kind == "silent" and diff.kind in ("new", "changed"):
                suppressed += 1
                print(f"[silent] {diff.listing.title}: {d.reason}")
                # 通知基準未満の新着もまとめメール末尾に1行で載せる
                # (2026-08-02 ユーザー要望。土地のみ等はここにも載せない)
                if (diff.kind == "new" and not dry_run
                        and d.reason.startswith("新着だがスコア")):
                    quiet_new.append((diff, score))

        # ⭐キープ物件の掲載終了 = 売れた可能性大。逃した事実も速報する
        keep_gone_texts: list[str] = []
        for info in keep_gone:
            if not dry_run:
                price = (f"{info['price_yen']:,}円" if info["price_yen"] is not None
                         else "価格不明")
                keep_gone_texts.append(
                    f"⭐ キープ物件が掲載終了(売れた可能性)\n"
                    f"物件名: {info['title']}\n価格: {price}\nURL: {info['url']}")
                notified += 1

        # メール1タップの⭐キープ登録の受付報告 (登録した瞬間の安心のため)
        keep_added_texts: list[str] = []
        for e in keep_new:
            if not dry_run:
                note = f"\nメモ: {e['note']}" if e.get("note") else ""
                keep_added_texts.append(
                    f"⭐ キープ登録を受け付けました (メール1タップ登録)\n"
                    f"URL: {e['url']}{note}\n"
                    "→ 追跡リスト入り。値下げ・記載変更・掲載終了を見張ります")
                notified += 1

        kanpo_on = config.get("kanpo", {}).get("enabled", True)
        attach = notify_cfg.get("email", {}).get("attach_report", True) \
            if notify_cfg.get("email") is not None else False
        heartbeat_on = notify_cfg.get("heartbeat", True)

        if bundle and (to_send or keep_gone_texts or quiet_new
                       or keep_added_texts):
            # まとめ送信 (2026-08-01 ユーザー要望): 1回の巡回 = 最大1通。
            # 定期便が未送信の日なら同じメールに同梱し、台帳レポートも添付する
            heartbeat_text = None
            if not dry_run and heartbeat_on:
                meta_store = Store(config.get("db_path", "data/listings.db"))
                today = jst_today()
                if meta_store.get_meta("last_mail_date") != today:
                    prev = set(json.loads(
                        meta_store.get_meta("heartbeat_uids") or "[]"))
                    heartbeat_text = build_heartbeat(items, kanpo_enabled=kanpo_on,
                                                     bundled=True, prev_uids=prev)
                    meta_store.set_meta("last_mail_date", today)
                    meta_store.set_meta("heartbeat_uids",
                                        json.dumps(_top_uids(items)))
                    print("[info] 定期便をまとめメールに同梱 (本日初回)")
                meta_store.close()
            if not dry_run:
                notifier.send_text(
                    build_patrol_summary(to_send, keep_gone_texts, heartbeat_text,
                                         quiet_new=quiet_new,
                                         keep_added_texts=keep_added_texts),
                    attachment=report_path if attach else None)
        elif not bundle:
            # 従来モード (config の notify.bundle: false で戻せる): 1件1通
            for diff, score in to_send:
                notifier.send(diff, score)
            for text in keep_gone_texts + keep_added_texts:
                notifier.send_text(text)

        # 毎日の定期便: 通知の有無に関係なく1日1回必ず送る (2026-07-31 修正)。
        # 官報チェックと注目上位を毎日届けるのが目的。送った日は meta に記録し、
        # 同日の以降の巡回では沈黙する (日曜はダイジェストが定期便を兼ねる)。
        # まとめ送信で同梱済みの日は meta が更新されているのでここは沈黙する。
        if not dry_run and heartbeat_on:
            meta_store = Store(config.get("db_path", "data/listings.db"))
            today = jst_today()
            if meta_store.get_meta("last_mail_date") != today:
                prev = set(json.loads(
                    meta_store.get_meta("heartbeat_uids") or "[]"))
                notifier.send_text(build_heartbeat(items, kanpo_enabled=kanpo_on,
                                                   notified=notified,
                                                   prev_uids=prev),
                                   attachment=report_path)
                meta_store.set_meta("last_mail_date", today)
                meta_store.set_meta("heartbeat_uids",
                                    json.dumps(_top_uids(items)))
                print("[info] 定期便を送信 (本日初回)")
            meta_store.close()

    # 従来モードのみ: 通知が出た巡回でレポート本体を別メール添付で届ける
    # (まとめ送信モードではまとめメールに添付済み)
    if report_path and not digest and not notify_cfg.get("bundle", True):
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
    ap.add_argument("--preview-bundle", action="store_true",
                    help="まとめメールの見た目確認用に1通だけ送る")
    ap.add_argument("--check", action="store_true",
                    help="設定の健康診断 (何が足りないかを日本語で表示)")
    ap.add_argument("--dry-run", action="store_true",
                    help="DB更新・通知をせずスコア順位を表示する")
    args = ap.parse_args()
    if args.check:
        sys.exit(self_check(args.config))
    try:
        sys.exit(run(args.config, dry_run=args.dry_run, report_path=args.report,
                     digest=args.digest, preview_bundle=args.preview_bundle))
    except ConfigError as e:
        print(f"[設定エラー] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
