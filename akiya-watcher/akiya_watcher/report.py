"""朝のレポート (HTML) 生成。

このページがツールの「顔」。毎朝これを開けば、
  1. 今すぐ自分の目で見るべき物件 (今回の値下げ・高スコア新着)
  2. 全物件の有望順ランキング (落とさない・不明は要確認として表示)
が1枚で分かる。スマホ閲覧を想定したシングルカラム。
"""
from __future__ import annotations

import html
from datetime import date
from urllib.parse import quote

from .alerts import offer_candidate_reason
from .criteria import estimate_disposal_cost_yen, is_keep, suggest_offer_yen
from .models import Listing, Score
from .storage import Diff

CSS = """
:root { --bg:#f6f4ef; --card:#fff; --ink:#2b2926; --sub:#6f6a62;
        --accent:#b0413e; --gold:#8a6d1d; --line:#e5e0d6; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#191713; --card:#232019; --ink:#e8e4da; --sub:#a39c8e;
          --accent:#e07570; --gold:#d4b45a; --line:#3a352c; }
  .badge { background:#322d22; }
  .badge.alert { background:#4a2422; }
  .unknown { background:#2c2921; }
  .copy { background:var(--card); color:var(--ink); }
  .inq { background:var(--card); color:var(--ink); }
}
.conclusion { font-size:1.02rem; font-weight:700; background:var(--card);
              border:1px solid var(--line); border-radius:10px;
              padding:12px 16px; margin-bottom:8px; }
.conclusion.urgent { border:2px solid var(--accent); color:var(--accent); }
* { box-sizing:border-box; margin:0; }
body { font-family:'Hiragino Sans','Noto Sans JP',sans-serif; background:var(--bg);
       color:var(--ink); line-height:1.6; padding:16px; max-width:720px; margin:0 auto; }
h1 { font-size:1.25rem; margin:8px 0 2px; }
.sub { color:var(--sub); font-size:.85rem; margin-bottom:16px; }
h2 { font-size:1rem; margin:24px 0 8px; padding-left:8px;
     border-left:4px solid var(--accent); }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:14px 16px; margin-bottom:12px; }
.card.hot { border:2px solid var(--accent); }
.rank { color:var(--sub); font-size:.8rem; }
.score { float:right; font-weight:700; color:var(--gold); font-size:1.05rem; }
.title { font-weight:700; margin:2px 0 4px; }
.price { font-size:1.05rem; font-weight:700; }
.price .old { color:var(--sub); text-decoration:line-through; font-weight:400;
              font-size:.85rem; margin-right:6px; }
.price .drop { color:var(--accent); }
.addr { color:var(--sub); font-size:.85rem; margin-bottom:6px; }
.badges { margin:6px 0; }
.badge { display:inline-block; background:#f0ece2; border-radius:999px;
         padding:2px 10px; font-size:.78rem; margin:2px 4px 2px 0; }
.badge.alert { background:#fbe4e3; color:var(--accent); font-weight:700; }
.badge.deal { background:#e2ecdf; color:#3d6b35; font-weight:700; }
.unknown { display:inline-block; background:#eee; color:var(--sub);
           border-radius:4px; padding:1px 8px; font-size:.75rem; margin:2px 4px 2px 0; }
details { margin-top:6px; }
summary { color:var(--sub); font-size:.8rem; cursor:pointer; }
.reasons { font-size:.8rem; color:var(--sub); padding-left:1.2em; margin-top:4px; }
a.link { display:inline-block; margin-top:8px; font-size:.85rem; color:#1a5276;
         text-decoration:none; font-weight:700; }
footer { color:var(--sub); font-size:.75rem; margin:24px 0; text-align:center; }
.offer-reason { color:var(--gold); font-size:.85rem; font-weight:700; margin:8px 0 -8px; }
.real { color:var(--accent); font-size:.9rem; font-weight:700; margin-top:2px; }
.inq { width:100%; font-size:.8rem; margin-top:6px; border:1px solid var(--line);
       border-radius:6px; padding:8px; font-family:inherit; }
.copy { margin-top:4px; padding:4px 14px; border:1px solid var(--gold);
        background:#fff; border-radius:6px; cursor:pointer; font-size:.8rem; }
.sold-row { background:var(--card); border:1px solid var(--line); border-radius:8px;
            padding:8px 12px; margin-bottom:6px; font-size:.85rem; color:var(--sub); }
"""


def _price_html(diff: Diff) -> str:
    ls, ctx = diff.listing, diff.context
    if ls.price_yen is None:
        return '<span class="price">価格不明 <small>(応相談? 指値候補)</small></span>'
    now = f"{ls.price_yen:,}円"
    if ctx.drop_pct:
        old = f"{ctx.previous_price_yen:,}円"
        return (f'<span class="price"><span class="old">{old}</span>'
                f'<span class="drop">{now} (▼{ctx.drop_pct}%)</span></span>')
    return f'<span class="price">{now}</span>'


INQUIRY_TEMPLATE = """お世話になります。掲載中の「{title}」({price})について、購入を前提に内見を希望いたします。

・残置物、家財はそのままの現状渡しで問題ありません(片付け不要です)
・現地確認のうえ、速やかにお返事いたします

最短で内見可能な日程をご教示ください。どうぞよろしくお願いいたします。"""


def _inquiry_html(ls: Listing) -> str:
    price = f"{ls.price_yen:,}円" if ls.price_yen is not None else "価格応相談"
    text = INQUIRY_TEMPLATE.format(title=ls.title[:60], price=price)
    return (f'<details><summary>✉ 問い合わせ文(コピーして送るだけ)</summary>'
            f'<textarea class="inq" readonly rows="7">{html.escape(text)}</textarea>'
            f'<button class="copy" onclick="navigator.clipboard.writeText('
            f'this.previousElementSibling.value);this.textContent=\'コピーしました\'">'
            f'コピー</button></details>')


def _card(rank: int, diff: Diff, score: Score, hot: bool = False,
          deal: dict | None = None) -> str:
    ls = diff.listing
    deal_chip = ""
    if deal:
        offer = (f" {deal['offer_yen'] / 10_000:,.0f}万" if deal.get("offer_yen") else "")
        deal_chip = f'<span class="badge deal">🤝{html.escape(deal["status"])}{offer}</span>'
    badges = "".join(
        f'<span class="badge{" alert" if b.startswith(("🔻", "🆕")) else ""}">{html.escape(b)}</span>'
        for b in score.badges)
    unknowns = "".join(f'<span class="unknown">要確認: {html.escape(u)}</span>'
                       for u in score.unknowns)
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in score.reasons)

    # 実質価格 = 表示価格 + 残置物片付け費の概算
    disposal = estimate_disposal_cost_yen(ls)
    real_price = ""
    if disposal and ls.price_yen is not None:
        real_price = (f'<div class="real">実質 約{(ls.price_yen + disposal) / 10_000:,.0f}万円 '
                      f'<small>(片付け費 約{disposal // 10_000}万円込みの目安)</small></div>')

    map_link = ""
    if ls.address:
        q = quote(ls.address)
        map_link = (f' <a class="link" href="https://www.google.com/maps/search/'
                    f'?api=1&query={q}">🗺 地図</a>')

    return f"""
<div class="card{' hot' if hot else ''}">
  <span class="score">{score.out_of_ten}<small>/10</small></span>
  <div class="rank">#{rank} <small>({html.escape(ls.source)})</small></div>
  <div class="title">{html.escape(ls.title)}</div>
  {_price_html(diff)}
  {real_price}
  <div class="addr">{html.escape(ls.address or '所在地不明')}</div>
  <div class="badges">{deal_chip}{badges}</div>
  <div>{unknowns}</div>
  <details><summary>スコア内訳 (素点{score.total}点を10点満点に換算)</summary>
  <ul class="reasons">{reasons}</ul></details>
  {_inquiry_html(ls)}
  <a class="link" href="{html.escape(ls.url)}">▶ 掲載ページを見る</a>{map_link}
</div>"""


def render_report(items: list[tuple[Diff, Score]], report_date: date | None = None,
                  offer_min_age_days: int = 90,
                  delisted: list[dict] | None = None,
                  deals: dict[str, dict] | None = None,
                  deal_history: list[dict] | None = None) -> str:
    """(Diff, Score) のリストから台帳レポートHTMLを生成する。"""
    report_date = report_date or date.today()
    items = sorted(items, key=lambda x: x[1].total, reverse=True)

    # 「今すぐ確認」= 今回値下げされた物件 + 高スコアの新着
    hot = [(d, s) for d, s in items
           if (d.context.price_changed and d.context.drop_pct)
           or (d.context.is_new and s.total >= 10)]
    hot_uids = {d.listing.uid for d, _ in hot}

    # 「指値候補」= 長期掲載 or 値下げ履歴あり (売主が譲歩し始めている)
    offers = [(d, s, offer_candidate_reason(d, offer_min_age_days)) for d, s in items]
    offers = [(d, s, r) for d, s, r in offers if r]

    deals = deals or {}

    def deal_of(d: Diff) -> dict | None:
        return deals.get(d.listing.uid)

    hot_html = "".join(_card(i + 1, d, s, hot=True, deal=deal_of(d))
                       for i, (d, s) in enumerate(hot)) \
        or '<p class="sub">本日は緊急案件なし。</p>'

    # ⭐キープ: 理想条件(残置物×立地)の常設コーナー
    keeps = [(d, s) for d, s in items if is_keep(s)]
    keep_html = "".join(_card(i + 1, d, s, deal=deal_of(d))
                        for i, (d, s) in enumerate(keeps)) \
        or '<p class="sub">現在、理想条件に合う物件なし。出たら自動でここに載ります。</p>'

    def _offer_line(d: Diff, reason: str) -> str:
        offer = suggest_offer_yen(
            d.listing.price_yen, d.context.age_days,
            has_drop_history=d.context.drop_pct is not None)
        tip = (f' → 指値の目安 <b>{offer / 10_000:,.0f}万円</b>' if offer else "")
        return f'<div class="offer-reason">🎯 {html.escape(reason)}{tip}</div>'

    offer_html = "".join(
        _offer_line(d, r) + _card(i + 1, d, s, deal=deal_of(d))
        for i, (d, s, r) in enumerate(offers)) \
        or '<p class="sub">現在、指値候補なし。</p>'
    all_html = "".join(_card(i + 1, d, s, hot=d.listing.uid in hot_uids,
                             deal=deal_of(d))
                       for i, (d, s) in enumerate(items))

    # 実戦データ: 指値・成約・見送りの記録 (通る指値を学ぶ)
    battle_html = ""
    if deal_history:
        rows = []
        for h in deal_history[:15]:
            offer = (f' 指値 {h["offer_yen"] / 10_000:,.0f}万円'
                     if h.get("offer_yen") else "")
            note = f' — {html.escape(h["note"])}' if h.get("note") else ""
            rows.append(f'<div class="sold-row">[{html.escape(h["status"])}]{offer} '
                        f'{html.escape((h["title"] or "")[:50])}{note}</div>')
        battle_html = (f'<h2>📓 実戦データ — あなたの商談記録 ({len(deal_history)}件)</h2>'
                       f'<p class="sub">通った指値・断られた指値の記録。'
                       f'貯まるほど「この地域で通る値段」が見えてくる。</p>'
                       + "".join(rows))

    # 掲載終了 (売れた?) — 相場観を貯める記録
    sold_html = ""
    if delisted:
        row_parts = []
        for x in delisted[:15]:
            price = f'{x["price_yen"]:,}円' if x["price_yen"] else "価格不明"
            row_parts.append(
                f'<div class="sold-row">{html.escape(x["title"][:60])} — {price}'
                f' / 掲載{x["days_on_market"]}日で終了'
                f' <a href="{html.escape(x["url"])}">↗</a></div>')
        sold_html = (f'<h2>⌛ 最近消えた物件 — 売れるスピードの記録 ({len(delisted)}件)</h2>'
                     f'<p class="sub">掲載終了 ≒ 売れた。「この価格帯は◯日で消える」という'
                     f'相場観がここに貯まる。</p>' + "".join(row_parts))

    drops = sum(1 for d, _ in items if d.context.price_changed and d.context.drop_pct)
    news = sum(1 for d, _ in items if d.context.is_new)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>物件台帳レポート {report_date.isoformat()}</title>
<style>{CSS}</style></head><body>
<h1>🏚 物件台帳レポート</h1>
<div class="sub">{report_date.isoformat()} | 監視 {len(items)}件 |
🔻本日の値下げ {drops}件 | 🆕新着 {news}件 | 🎯指値候補 {len(offers)}件</div>
{f'<div class="conclusion urgent">🚨 今すぐ見るべき物件が {len(hot)}件 あります</div>'
 if hot else '<div class="conclusion">きょうは大きな動きなし。指値候補だけ眺めてください。</div>'}
<h2>🚨 今すぐ自分の目で見る ({len(hot)}件)</h2>
{hot_html}
<h2>⭐ キープ — 理想条件: 残置物 × 立地 ({len(keeps)}件)</h2>
<p class="sub">この条件の物件は常時ここに載ります。値下げ・記載変更・掲載終了が
あれば、通常なら知らせない小さな変化でも即通知します。</p>
{keep_html}
<h2>🎯 指値候補 — 待たずに攻める ({len(offers)}件)</h2>
<p class="sub">長期掲載・値下げ履歴 = 売主が譲歩し始めているサイン。
値下げを待つのではなく、こちらから大幅指値を入れる候補。</p>
{offer_html}
<h2>📋 全物件ランキング (落とさず有望順)</h2>
{all_html}
{sold_html}
{battle_html}
<footer>akiya-watcher — 除外しない。並べて、人間が決める。</footer>
</body></html>"""
