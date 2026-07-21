"""通知ゲート — 「何もない日は何も来ない」を守る層。

設計思想の二層構造:
  - 台帳(レポート)側は絶対に落とさない。全物件がスコア順に残る。
  - 通知(割り込み)側は厳選する。鳴ったら「ほぼ確実に見る価値がある」状態を保つ。

通知ルール:
  1. 値下げの瞬間は原則すべて通知 (ツールの存在理由)
  2. 新着はスコアが閾値以上のときだけ通知
  3. 「土地のみ・山林・原野」は通知しない (台帳には残る)
  4. 倒壊級の記載がある物件は通知の閾値を上げる (廃墟スパム防止)
  5. 値下げを伴わない掲載変更は通知しない (台帳で追える)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import Listing, Score
from .storage import Diff

# 建物が無い(またはほぼ無い)ことを示す表現。通知対象外の判定に使う。
LAND_ONLY_PAT = re.compile(r"土地のみ|売地|更地|山林|原野|農地|田畑|雑種地")

# 建物が有ることを示す表現。「山林付きの家」(家+山)を土地のみと誤判定しない。
BUILDING_PAT = re.compile(
    r"平屋|[0-9]階建|階建て|戸建|一戸建|住宅|古民家|家屋"
    r"|[0-9]S?LDK|[0-9]LDK|[0-9]DK|[0-9]K(?![0-9])")

# 建て直し前提レベルの損壊。除外はしないが通知ハードルを上げる。
RUIN_PAT = re.compile(r"倒壊|全壊|半壊|崩落|廃屋|住居利用不可")


def looks_land_only(ls: Listing) -> bool:
    """建物情報が無く、土地系キーワードだけの掲載か。"""
    blob = unicodedata.normalize("NFKC", f"{ls.title} {ls.description}")
    has_building_signal = bool(ls.floor_area_sqm or ls.layout
                               or BUILDING_PAT.search(blob))
    return bool(LAND_ONLY_PAT.search(blob)) and not has_building_signal


def looks_ruin(ls: Listing) -> bool:
    return bool(RUIN_PAT.search(f"{ls.title} {ls.description}"))


@dataclass
class AlertDecision:
    notify: bool
    kind: str      # "drop" | "new" | "silent"
    reason: str    # ログ用: なぜ通知した/しなかったか


def decide(diff: Diff, score: Score, min_score: int = 8,
           ruin_extra: int = 5) -> AlertDecision:
    ls, ctx = diff.listing, diff.context

    if looks_land_only(ls):
        return AlertDecision(False, "silent", "土地のみ掲載のため通知対象外(台帳には掲載)")

    threshold = min_score + (ruin_extra if looks_ruin(ls) else 0)

    # 値下げの瞬間 — 原則通知。廃墟級のみ閾値を課す
    if ctx.price_changed and ctx.drop_pct:
        if looks_ruin(ls) and score.total < threshold:
            return AlertDecision(False, "silent",
                                 f"値下げだが損壊記載あり・スコア{score.total}<閾値{threshold}")
        return AlertDecision(True, "drop", f"値下げ▼{ctx.drop_pct}%")

    # 新着 — スコア閾値以上のみ
    if diff.kind == "new":
        if score.total >= threshold:
            return AlertDecision(True, "new", f"新着 スコア{score.total}≥{threshold}")
        return AlertDecision(False, "silent",
                             f"新着だがスコア{score.total}<閾値{threshold}(台帳には掲載)")

    # 値下げを伴わない変更・変化なし — 沈黙
    return AlertDecision(False, "silent", "値下げなし")


def offer_candidate_reason(diff: Diff, min_age_days: int = 90) -> str | None:
    """指値候補(売主が譲歩し始めている物件)なら理由文字列を返す。

    値下げの瞬間を「待つ」のではなく「起こす」ための攻めのリスト。
    - 長期掲載: 問い合わせが無く売主が疲弊し始めている可能性
    - 値下げ履歴: 一度譲歩した売主は再度譲歩しやすい
    """
    if looks_land_only(diff.listing):
        return None
    reasons = []
    if diff.context.age_days >= min_age_days:
        reasons.append(f"掲載{diff.context.age_days}日")
    if diff.context.drop_pct:
        reasons.append(f"値下げ履歴▼{diff.context.drop_pct}%")
    return "・".join(reasons) if reasons else None
