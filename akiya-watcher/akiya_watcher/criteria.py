"""スコアリングロジック。

設計思想: 条件で物件を「落とす」のではなく、有望さをスコア化して並べる。
情報が無い項目は減点せず「不明・要確認」として残す。絞りすぎて見逃すことが
最も避けたい失敗である。

最重要シグナル(重い順):
  1. 大幅値下げ・新着 (「値下げの瞬間」を逃さないことがツールの存在理由)
  2. 残置物・家財・現状渡し (他の条件を上書きするほど重要)
  3. 相続・遠方所有・管理困難など「手放したい事情」がにじむ記載
  4. 駐車場の広さ (1台は欲しい、5台前後なら理想)
  5. 生活利便性 (スーパー・小中学校が近い = 買った後に活用できる立地)

表記揺れ(「198万円」「並列2台可」「簡易水洗」等)を正規化するパーサ群も
ここに集約する。すべて純関数/純クラスなのでオフラインで単体テストできる。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import Listing, ListingContext, Score

# ---------------------------------------------------------------- パーサ群


def _normalize(text: str) -> str:
    """全角数字・記号を半角へ、空白を除去して表記揺れを吸収する。"""
    return unicodedata.normalize("NFKC", text or "").replace(" ", "").replace("　", "")


def parse_price_yen(text: str) -> int | None:
    """価格表記を円に変換する。例: "198万円"→1980000, "1,980,000円"→1980000。

    0円物件(無償譲渡)は 0 を返す。不明は None (0とNoneは意味が違う)。
    """
    t = _normalize(text)
    if not t:
        return None
    if re.search(r"(?<![0-9,.])0円|無償譲渡|無償|0円物件", t):
        return 0
    m = re.search(r"([0-9,]+(?:\.[0-9]+)?)億", t)
    oku = float(m.group(1).replace(",", "")) if m else 0.0
    rest = t[m.end():] if m else t
    m = re.search(r"([0-9,]+(?:\.[0-9]+)?)万", rest)
    if m or oku:
        man = float(m.group(1).replace(",", "")) if m else 0.0
        return int(oku * 100_000_000 + man * 10_000)
    m = re.search(r"([0-9,]{4,})円?", t)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def parse_area_sqm(text: str) -> float | None:
    """面積表記を㎡に変換する。例: "103.5㎡", "延床120m2", "80平米"。"""
    t = _normalize(text)
    m = re.search(r"([0-9,]+(?:\.[0-9]+)?)(?:㎡|m2|平米|平方メートル)", t, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def parse_layout_rooms(layout: str) -> int | None:
    """間取り表記から居室数を取り出す。例: "4LDK"→4, "5DK+S"→5。"""
    t = _normalize(layout)
    m = re.search(r"([0-9]+)\s*(?:S?LDK|LDK|DK|K|R)", t, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def parse_parking_slots(text: str) -> int | None:
    """駐車場の記載から駐車可能台数を推定する。

    "駐車場:3台"「並列2台可」「駐車スペース2台分」などを拾う。
    「駐車場あり」だけなら 1 台とみなす。記載がなければ None。
    """
    t = _normalize(text)
    if not t:
        return None
    best: int | None = None
    for m in re.finditer(r"(?:駐車|カースペース|ガレージ|車庫)[^0-9台]{0,12}([0-9]+)台", t):
        n = int(m.group(1))
        best = n if best is None else max(best, n)
    if best is None:
        for m in re.finditer(r"(?:並列|縦列)([0-9]+)台", t):
            n = int(m.group(1))
            best = n if best is None else max(best, n)
    if best is None and re.search(r"駐車場?(?:あり|有り?|付き?)", t):
        best = 1
    return best


FLUSH_TOILET_PAT = re.compile(r"水洗|下水道?|公共下水|浄化槽")
NON_FLUSH_PAT = re.compile(r"汲み?取り?|くみ取り?|簡易水洗")


def is_flush_toilet(text: str) -> bool | None:
    """水洗トイレ(公共下水・浄化槽)かどうか。判別不能なら None。

    「簡易水洗」は実態が汲み取りなので水洗とはみなさない。
    """
    t = _normalize(text)
    if not t:
        return None
    if NON_FLUSH_PAT.search(t):
        return False
    if FLUSH_TOILET_PAT.search(t):
        return True
    return None

# ---------------------------------------------------------------- キーワード群

# 残置物系: 最重要。買い手に敬遠され交渉しやすく、処分権が引き継がれれば
# 価値ある品が残っている可能性もある。
ZANCHI_KEYWORDS = [
    "残置物", "家財", "未片付け", "現状渡し", "現状引き渡し", "現状有姿",
]


@dataclass(frozen=True)
class ZanchiAssessment:
    """残置物と引渡し条件の判定結果。

    単に「残置物」という語があるだけでは、売主撤去の物件まで候補に入る。
    そこで、残ることが確定・存在のみ明示・現状有姿のみ・撤去の4段階に分ける。
    """

    status: str
    evidence: tuple[str, ...] = ()

    @property
    def is_candidate(self) -> bool:
        return self.status in {"confirmed", "present", "as_is"}

    @property
    def label(self) -> str:
        return {
            "confirmed": "A 確定（残置物ごと引渡し）",
            "present": "B 残置物あり（処分条件を要確認）",
            "as_is": "C 現状有姿のみ（残置物の有無を要確認）",
            "removal": "対象外（売主撤去・撤去済み）",
            "none": "記載なし",
        }[self.status]

    @property
    def line(self) -> str:
        why = f" / 根拠: {'、'.join(self.evidence)}" if self.evidence else ""
        return f"残置物判定: {self.label}{why}"


# 掲載文で実際に使われる表現を、意味ごとに分離する。
# 判定順は「撤去」優先。例:「残置物あり。売主負担で撤去」は候補にしない。
_ZANCHI_REMOVAL_PATTERNS = [
    ("売主側で撤去", re.compile(
        r"(?:残置物|家財|家具).{0,16}(?:売主|所有者|貸主|家主).{0,10}"
        r"(?:負担|撤去|処分|片付|整理)")),
    ("売主側で撤去", re.compile(
        r"(?:売主|所有者|貸主|家主).{0,10}(?:負担|撤去|処分|片付|整理)"
        r".{0,16}(?:残置物|家財|家具)")),
    ("売主側で撤去", re.compile(
        r"(?:売主|所有者|貸主|家主).{0,10}(?:残置物|家財|家具).{0,10}"
        r"(?:負担|撤去|処分|片付|整理)")),
    ("撤去・処分予定", re.compile(
        r"(?:残置物|家財|家具).{0,12}(?:撤去|処分|片付|整理)(?:の)?(?:予定|見込)")),
    ("撤去・処分済み", re.compile(
        r"(?:残置物|家財|家具).{0,12}(?:撤去|処分|片付|整理)(?:済み?|完了)")),
    ("残置物なし", re.compile(
        r"(?:残置物|家財|家具)(?:は)?(?:なし|無し|無い|無(?=$|[。、・,/]))")),
    ("引渡し前に撤去", re.compile(
        r"引(?:き)?渡しまでに.{0,16}(?:残置物|家財|家具).{0,12}"
        r"(?:撤去|処分|片付|整理)")),
]

_ZANCHI_PRESENCE_PATTERNS = [
    ("残置物", re.compile(r"残置物")),
    ("家財", re.compile(
        r"家財(?:道具)?(?:あり|有り|有|残置|が残|一式|込み|付き?|そのまま)")),
    ("家具・日用品", re.compile(
        r"(?:家具|日用品|生活用品|荷物).{0,8}(?:あり|有り|有|残置|が残|込み|付き?|そのまま)")),
    ("未片付け", re.compile(r"未片付け|片付け未了|整理未了")),
]

_AS_IS_PATTERNS = [
    ("現状渡し", re.compile(r"現状(?:のまま)?(?:渡し|引(?:き)?渡し)")),
    ("現況渡し", re.compile(r"現況(?:のまま)?(?:渡し|引(?:き)?渡し)")),
    ("現状有姿", re.compile(r"現状有姿")),
    ("現況有姿", re.compile(r"現況有姿")),
    ("そのまま引渡し", re.compile(r"そのまま(?:で)?引(?:き)?渡し")),
]

_BUYER_TAKES_PATTERNS = [
    ("買主負担", re.compile(
        r"(?:残置物|家財|家具).{0,16}(?:買主|購入者|利用者).{0,10}"
        r"(?:負担|撤去|処分|片付|整理)")),
    ("買主負担", re.compile(
        r"(?:買主|購入者|利用者).{0,10}(?:負担|撤去|処分|片付|整理)"
        r".{0,16}(?:残置物|家財|家具)")),
    ("買主負担", re.compile(
        r"(?:買主|購入者|利用者).{0,10}(?:残置物|家財|家具).{0,10}"
        r"(?:負担|撤去|処分|片付|整理)")),
    ("残置物も譲渡", re.compile(
        r"(?:残置物|家財|家具).{0,8}(?:も)?(?:譲渡|込み|含む|付ける)")),
    ("片付け不要", re.compile(r"片付け不要|撤去不要|処分不要")),
]


def assess_zanchi(ls: Listing,
                   extra_keywords: list[str] | None = None) -> ZanchiAssessment:
    """物件文から残置物の有無と引渡し条件を4段階判定する。"""
    raw_text = str(ls.raw.get("text", "") or "")
    blob = _normalize(" ".join([ls.title, ls.description, raw_text]))

    def hits(patterns: list[tuple[str, re.Pattern]]) -> list[str]:
        return [label for label, pattern in patterns if pattern.search(blob)]

    removal = hits(_ZANCHI_REMOVAL_PATTERNS)
    if removal:
        return ZanchiAssessment("removal", tuple(dict.fromkeys(removal)))

    presence = hits(_ZANCHI_PRESENCE_PATTERNS)
    if extra_keywords:
        presence.extend(kw for kw in extra_keywords if _normalize(kw) in blob)
    presence = list(dict.fromkeys(presence))
    as_is = list(dict.fromkeys(hits(_AS_IS_PATTERNS)))
    buyer_takes = list(dict.fromkeys(hits(_BUYER_TAKES_PATTERNS)))

    if presence and (as_is or buyer_takes):
        evidence = tuple(dict.fromkeys(presence + as_is + buyer_takes))
        return ZanchiAssessment("confirmed", evidence)
    if presence:
        return ZanchiAssessment("present", tuple(presence))
    if as_is:
        return ZanchiAssessment("as_is", tuple(as_is))
    return ZanchiAssessment("none")

# 売主事情系: 相続・遠方・管理困難など「手放したい事情」がにじむ表現。
# 公開された説明文の記載だけを対象にする(個人情報の収集・推測はしない)。
MOTIVE_KEYWORDS = [
    "相続", "空き家", "遠方", "管理困難", "管理が困難", "早期", "処分",
    "売り急ぎ", "価格応談", "値下げしました", "お引き取り",
]

# 生活利便系: 買った後に活用できる立地かどうか。
CONVENIENCE_KEYWORDS = [
    "スーパー", "小学校", "中学校", "コンビニ", "病院", "駅", "バス停", "徒歩",
]

# 再生コスト系: 除外はしないが把握しておきたい表現。
REPAIR_KEYWORDS = ["要補修", "要修繕", "要リフォーム", "古家", "解体前提", "雨漏り", "傾き"]

# 蔵・旧家系: 裕福な家系の物件を示す表現。貴金属・骨董・古道具が残置物に
# 含まれる期待値が最も高い、このプロジェクトの本丸シグナル。
# 注意: 「蔵」単体は「冷蔵庫」に誤反応するため、必ず複合語で書くこと。
WEALTH_KEYWORDS = [
    "土蔵", "蔵付", "蔵あり", "蔵有",
    "納屋", "母屋", "離れ", "旧家", "屋敷", "豪邸",
    "庭園", "庭石", "書院", "床の間", "欄間", "茶室",
]

# ---------------------------------------------------------------- キープ判定


def is_keep(score: "Score") -> bool:
    """ユーザーの理想条件: 残置物あり × (立地が良い または 蔵・旧家)。

    本当の狙いは裕福な家系の残置物(貴金属・骨董)。蔵・旧家シグナルは
    立地と同格のキープ条件とする。該当物件はレポートの⭐キープ欄に常設され、
    値下げ・記載変更・掲載終了があれば即時通知される。
    """
    return ("🪑残置物" in score.badges
            and ("🏺蔵・旧家" in score.badges
                 or "🏪利便" in score.badges or "📍注力" in score.badges))


# ---------------------------------------------------------------- 判断支援


def estimate_disposal_cost_yen(ls: Listing) -> int | None:
    """残置物の片付け費のざっくり概算。残置物系の記載がある物件のみ。

    間取りベースの経験則 (1R:10-15万 〜 4LDK:25-50万) の中央付近を取る。
    表示価格に足して「実質価格」として判断材料にする。あくまで目安。
    """
    if assess_zanchi(ls).status not in {"confirmed", "present"}:
        return None
    rooms = parse_layout_rooms(ls.layout)
    if rooms is None and ls.floor_area_sqm:
        rooms = max(1, int(ls.floor_area_sqm // 20))
    rooms = rooms or 3
    return min(100_000 + 60_000 * rooms, 500_000)


def suggest_offer_yen(price_yen: int | None, age_days: int = 0,
                      has_drop_history: bool = False) -> int | None:
    """指値の目安。売主の疲弊度(掲載期間・値下げ履歴)が強いほど深く指す。

    経験則: 長期掲載180日超→6割 / 値下げ履歴あり→65% / 90日超→7割。
    1万円単位に丸める。あくまで交渉の出発点。
    """
    if not price_yen:
        return None
    if age_days >= 180:
        factor = 0.60
    elif has_drop_history:
        factor = 0.65
    elif age_days >= 90:
        factor = 0.70
    else:
        return None
    return int(price_yen * factor) // 10_000 * 10_000


# ---------------------------------------------------------------- スコアラー


class Scorer:
    """Listing と履歴 (ListingContext) から Score を算出する。

    どの項目も「不合格」を作らない。減点はあっても除外はない。
    config.yaml の criteria セクションでエリア・キーワードを上書きできる。
    """

    def __init__(self, criteria: dict | None = None):
        criteria = criteria or {}
        self.priority_cities = criteria.get("priority_cities", [])
        # 既定判定は意味解析を使う。設定に追加語がある場合だけ補助シグナルにする。
        self.zanchi_kw = criteria.get("zanchi_keywords")
        self.wealth_kw = criteria.get("wealth_keywords", WEALTH_KEYWORDS)
        self.motive_kw = criteria.get("motive_keywords", MOTIVE_KEYWORDS)
        self.convenience_kw = criteria.get("convenience_keywords", CONVENIENCE_KEYWORDS)
        self.repair_kw = criteria.get("repair_keywords", REPAIR_KEYWORDS)

    def score(self, ls: Listing, ctx: ListingContext | None = None) -> Score:
        ctx = ctx or ListingContext(current_price_yen=ls.price_yen)
        s = Score()
        blob = " ".join([ls.title, ls.description, ls.toilet, ls.layout, ls.address])

        # --- 1. 鮮度シグナル: 値下げ・新着・長期掲載 -------------------
        drop = ctx.drop_pct
        if drop is not None and drop > 0:
            old = f"{ctx.previous_price_yen:,}円"
            new = f"{ctx.current_price_yen:,}円"
            if drop >= 40:
                s.add(6, f"大幅値下げ {old}→{new}", f"🔻値下げ{drop}%")
            elif drop >= 20:
                s.add(4, f"値下げ {old}→{new}", f"🔻値下げ{drop}%")
            else:
                s.add(2, f"値下げ {old}→{new}", f"🔻値下げ{drop}%")
        elif ctx.is_new:
            s.add(2, "新着", "🆕新着")
        if ctx.age_days >= 180:
            s.add(3, f"長期掲載 {ctx.age_days}日 (指値余地)", f"⏳{ctx.age_days}日")
        elif ctx.age_days >= 90:
            s.add(2, f"長期掲載 {ctx.age_days}日", f"⏳{ctx.age_days}日")

        # --- 2. 残置物 (最重要シグナル) --------------------------------
        # 「残置物は売主負担で撤去」のような逆条件を誤って加点しない。
        zanchi = assess_zanchi(ls, self.zanchi_kw)
        s.matched_keywords += list(zanchi.evidence)
        if zanchi.status == "confirmed":
            s.add(6, "残置物ごと引渡し: " + "、".join(zanchi.evidence), "🪑残置物")
            s.badges.append("✅そのまま引渡し")
        elif zanchi.status == "present":
            s.add(5, "残置物あり: " + "、".join(zanchi.evidence), "🪑残置物")
            s.badges.append("❓処分条件")
        elif zanchi.status == "as_is":
            s.add(2, "現状有姿: " + "、".join(zanchi.evidence), "📦現状有姿")
            s.unknowns.append("残置物の有無・処分条件")
        elif zanchi.status == "removal":
            s.badges.append("🧹残置物撤去")
            s.reasons.append("残置物は売主撤去・撤去済み: "
                             + "、".join(zanchi.evidence) + " (±0)")

        # --- 2.5. 蔵・旧家 (裕福な家系 = 残置物の期待値が最も高い本丸) -----
        wealth = [kw for kw in self.wealth_kw if kw in blob]
        if wealth:
            s.matched_keywords += wealth
            s.add(4, "蔵・旧家系: " + "、".join(wealth), "🏺蔵・旧家")

        # --- 3. 売主事情 ------------------------------------------------
        motive = [kw for kw in self.motive_kw if kw in blob]
        if zanchi.status == "removal":
            # 「残置物を処分する」の処分は売り急ぎの事情ではない。
            motive = [kw for kw in motive if kw != "処分"]
        if motive:
            s.matched_keywords += motive
            s.add(3, "売主事情: " + "、".join(motive), "🏠売主事情")

        # --- 4. 価格 ----------------------------------------------------
        p = ls.price_yen
        if p is None:
            s.unknowns.append("価格(応相談? 指値候補)")
        elif p == 0:
            s.add(4, "0円(無償譲渡)物件", "💴0円")
        elif p <= 1_000_000:
            s.add(4, f"価格 {p:,}円", "💴100万以下")
        elif p <= 2_000_000:
            s.add(3, f"価格 {p:,}円", "💴200万以下")
        elif p <= 3_000_000:
            s.add(2, f"価格 {p:,}円")
        elif p <= 5_000_000:
            s.add(1, f"価格 {p:,}円")

        # --- 5. 駐車場 (1台は欲しい、5台前後なら理想) --------------------
        slots = ls.parking_slots
        if slots is None:
            slots = parse_parking_slots(blob)
        if slots is not None:
            if slots >= 5:
                s.add(4, f"駐車 {slots}台 (理想)", f"🚗{slots}台")
            elif slots >= 2:
                s.add(2, f"駐車 {slots}台", f"🚗{slots}台")
            else:
                s.add(1, f"駐車 {slots}台")
        elif ls.land_area_sqm and ls.land_area_sqm >= 300:
            s.add(3, f"敷地 {ls.land_area_sqm:,.0f}㎡ (複数台の余地)", "🚗敷地広")
        elif ls.land_area_sqm and ls.land_area_sqm >= 200:
            s.add(2, f"敷地 {ls.land_area_sqm:,.0f}㎡ (駐車余地)", "🚗敷地広")
        else:
            s.unknowns.append("駐車場")

        # --- 6. トイレ (汲み取りは減点、ただし除外しない) -----------------
        flush = is_flush_toilet(ls.toilet or blob)
        if flush is True:
            s.add(1, "水洗トイレ")
        elif flush is False:
            s.add(-2, "汲み取り式 (改修コスト)", "⚠️汲み取り")
        else:
            s.unknowns.append("トイレ形式")

        # --- 7. 生活利便性 (買った後に活用できる立地か) -------------------
        conv = [kw for kw in self.convenience_kw if kw in blob]
        if conv:
            s.add(min(len(conv), 3), "生活利便: " + "、".join(conv), "🏪利便")
        else:
            s.unknowns.append("周辺環境(スーパー・学校)")

        # --- 8. 建物規模 (参考条件) -------------------------------------
        rooms = parse_layout_rooms(ls.layout)
        if (ls.floor_area_sqm and ls.floor_area_sqm >= 80) or (rooms and rooms >= 4):
            s.add(1, f"建物規模 {ls.floor_area_sqm or ''}㎡ {ls.layout}".strip())

        # --- 9. エリア --------------------------------------------------
        if any(city in ls.address for city in self.priority_cities):
            s.add(1, "注力エリア", "📍注力")

        # --- 10. 再生コストの把握 (減点なし・情報として付記) ---------------
        repair = [kw for kw in self.repair_kw if kw in blob]
        if repair:
            s.matched_keywords += repair
            s.reasons.append("補修系記載: " + "、".join(repair) + " (±0)")

        return s
