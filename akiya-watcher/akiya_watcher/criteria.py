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
    "残置物", "家財", "家具", "未片付け", "現状渡し", "現状引き渡し", "現状有姿",
]

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

# ---------------------------------------------------------------- 判断支援


def estimate_disposal_cost_yen(ls: Listing) -> int | None:
    """残置物の片付け費のざっくり概算。残置物系の記載がある物件のみ。

    間取りベースの経験則 (1R:10-15万 〜 4LDK:25-50万) の中央付近を取る。
    表示価格に足して「実質価格」として判断材料にする。あくまで目安。
    """
    blob = f"{ls.title} {ls.description}"
    if not any(kw in blob for kw in ZANCHI_KEYWORDS):
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
        self.zanchi_kw = criteria.get("zanchi_keywords", ZANCHI_KEYWORDS)
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
        zanchi = [kw for kw in self.zanchi_kw if kw in blob]
        if zanchi:
            s.matched_keywords += zanchi
            s.add(4 + min(len(zanchi) - 1, 2), "残置物系: " + "、".join(zanchi), "🪑残置物")

        # --- 3. 売主事情 ------------------------------------------------
        motive = [kw for kw in self.motive_kw if kw in blob]
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
