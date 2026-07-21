"""朝のレポート (HTML) 生成。

このページがツールの「顔」。毎朝これを開けば、
  1. 今すぐ自分の目で見るべき物件 (今回の値下げ・高スコア新着)
  2. 全物件の有望順ランキング (落とさない・不明は要確認として表示)
が1枚で分かる。スマホ閲覧を想定したシングルカラム。
"""
from __future__ import annotations

import html
from datetime import date

from .models import Listing, Score
from .storage import Diff

CSS = """
:root { --bg:#f6f4ef; --card:#fff; --ink:#2b2926; --sub:#6f6a62;
        --accent:#b0413e; --gold:#8a6d1d; --line:#e5e0d6; }
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
.unknown { display:inline-block; background:#eee; color:var(--sub);
           border-radius:4px; padding:1px 8px; font-size:.75rem; margin:2px 4px 2px 0; }
details { margin-top:6px; }
summary { color:var(--sub); font-size:.8rem; cursor:pointer; }
.reasons { font-size:.8rem; color:var(--sub); padding-left:1.2em; margin-top:4px; }
a.link { display:inline-block; margin-top:8px; font-size:.85rem; color:#1a5276;
         text-decoration:none; font-weight:700; }
footer { color:var(--sub); font-size:.75rem; margin:24px 0; text-align:center; }
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


def _card(rank: int, diff: Diff, score: Score, hot: bool = False) -> str:
    ls = diff.listing
    badges = "".join(
        f'<span class="badge{" alert" if b.startswith(("🔻", "🆕")) else ""}">{html.escape(b)}</span>'
        for b in score.badges)
    unknowns = "".join(f'<span class="unknown">要確認: {html.escape(u)}</span>'
                       for u in score.unknowns)
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in score.reasons)
    return f"""
<div class="card{' hot' if hot else ''}">
  <span class="score">{score.total}点</span>
  <div class="rank">#{rank} <small>({html.escape(ls.source)})</small></div>
  <div class="title">{html.escape(ls.title)}</div>
  {_price_html(diff)}
  <div class="addr">{html.escape(ls.address or '所在地不明')}</div>
  <div class="badges">{badges}</div>
  <div>{unknowns}</div>
  <details><summary>スコア内訳</summary><ul class="reasons">{reasons}</ul></details>
  <a class="link" href="{html.escape(ls.url)}">▶ 掲載ページを見る</a>
</div>"""


def render_report(items: list[tuple[Diff, Score]], report_date: date | None = None) -> str:
    """(Diff, Score) のリストから朝のレポートHTMLを生成する。"""
    report_date = report_date or date.today()
    items = sorted(items, key=lambda x: x[1].total, reverse=True)

    # 「今すぐ確認」= 今回値下げされた物件 + 高スコアの新着
    hot = [(d, s) for d, s in items
           if (d.context.price_changed and d.context.drop_pct)
           or (d.context.is_new and s.total >= 10)]
    hot_uids = {d.listing.uid for d, _ in hot}

    hot_html = "".join(_card(i + 1, d, s, hot=True) for i, (d, s) in enumerate(hot)) \
        or '<p class="sub">本日は緊急案件なし。</p>'
    all_html = "".join(_card(i + 1, d, s, hot=d.listing.uid in hot_uids)
                       for i, (d, s) in enumerate(items))

    drops = sum(1 for d, _ in items if d.context.price_changed and d.context.drop_pct)
    news = sum(1 for d, _ in items if d.context.is_new)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>朝の物件レポート {report_date.isoformat()}</title>
<style>{CSS}</style></head><body>
<h1>🏚 朝の物件レポート</h1>
<div class="sub">{report_date.isoformat()} | 監視 {len(items)}件 |
🔻本日の値下げ {drops}件 | 🆕新着 {news}件</div>
<h2>🚨 今すぐ自分の目で見る ({len(hot)}件)</h2>
{hot_html}
<h2>📋 全物件ランキング (落とさず有望順)</h2>
{all_html}
<footer>akiya-watcher — 除外しない。並べて、人間が決める。</footer>
</body></html>"""
