"""物件よみとり — 仕入れ点(売主の困り気配)の採点エンジン。

卒業制作フェーズ1。設計書(docs/卒業制作_設計書.md)のルーブリックを実装する。

設計の経緯 (2026-08-02):
- 当初はLLM API(Claude API)での採点を計画したが、APIキー・課金なしの
  運用が条件になった。GitHub Models(GITHUB_TOKENの無料推論)も実地テストの
  結果、サービス廃止進行中(410 retirement brownout)と判明
- そこで方針転換: 実戦とAIとの対話で得た判断基準を「重み付きルール」として
  コードに焼き付けた。無料・決定的(テスト可能)・外部依存ゼロで永続する。
  将来LLMを足す場合もこのモジュールを差し替えるだけでよい

採点の思想 (実戦の学びそのもの):
- 学び①「狙うべきは、中身が売主にとって面倒なゴミの山に見えている家」
- 高得点 = 売主が手放したがっている気配が濃い = 「残置物ごと・安く」が通りやすい
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import Listing, ListingContext

# (名前, 正規表現, 加点, 理由ラベル)
# 重みは実戦の学び順: 残置物・現状渡し > 相続・遠方 > 売り急ぎ > 付属建物
_SIGNALS: list[tuple[str, re.Pattern, int, str]] = [
    ("zanchi", re.compile(r"残置物|家財|現状渡し|現状有姿|そのまま|残った(まま|状態)"),
     25, "残置物・現状渡しの文言"),
    ("souzoku", re.compile(r"相続|実家|父|母|両親|故人|遺品"),
     15, "相続の気配"),
    ("enpou", re.compile(r"遠方|県外|管理でき|帰省|帰れ|住んでい(ない|ません)"),
     15, "遠方管理の気配"),
    ("uriisogi", re.compile(r"早[くめ]|急ぎ|処分|手放し|お譲り|引き取|讓渡|譲渡"),
     10, "売り急ぎの表現"),
    ("fuzoku", re.compile(r"蔵|納屋|倉庫|物置|離れ|作業場|車庫"),
     10, "付属建物あり(中身が面倒の種)"),
]

_NEGATIVE: list[tuple[str, re.Pattern, int, str]] = [
    ("reform", re.compile(r"リフォーム済|リノベーション済|改装済|クリーニング済|修繕済"),
     -15, "手入れ済み(売主は強気)"),
]


@dataclass
class Reading:
    """仕入れ点の採点結果。scoreは0〜100、reasonsは根拠ラベル(強い順)。"""
    score: int
    reasons: list[str]

    @property
    def line(self) -> str:
        """通知メールに載せる1行。例: 「仕入れ点: 70/100 (残置物・現状渡しの文言、相続の気配)」"""
        why = "、".join(self.reasons[:3]) if self.reasons else "特筆する気配なし"
        return f"仕入れ点: {self.score}/100 ({why})"


def read_listing(ls: Listing, ctx: ListingContext | None = None) -> Reading:
    """物件の文章と履歴から「売主の困り気配」を0〜100で採点する。"""
    blob = unicodedata.normalize("NFKC", f"{ls.title} {ls.description}")
    score = 0
    hits: list[tuple[int, str]] = []

    for _, pat, points, label in _SIGNALS:
        if pat.search(blob):
            score += points
            hits.append((points, label))
    for _, pat, points, label in _NEGATIVE:
        if pat.search(blob):
            score += points
            hits.append((abs(points), f"減点: {label}"))

    if ctx is not None:
        # 値下げ履歴: 一度譲歩した売主は再度譲歩しやすい。幅が大きいほど濃い
        if ctx.drop_pct:
            points = min(20, 5 + ctx.drop_pct // 10 * 5)
            score += points
            hits.append((points, f"値下げ履歴▼{ctx.drop_pct}%"))
        # 長期掲載: 問い合わせがなく売主が疲弊し始めている可能性
        if ctx.age_days >= 180:
            score += 15
            hits.append((15, f"長期掲載{ctx.age_days}日"))
        elif ctx.age_days >= 90:
            score += 10
            hits.append((10, f"長期掲載{ctx.age_days}日"))

    hits.sort(key=lambda x: x[0], reverse=True)
    return Reading(score=max(0, min(100, score)),
                   reasons=[label for _, label in hits])
