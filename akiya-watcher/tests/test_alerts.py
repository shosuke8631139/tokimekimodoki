"""通知ゲート・指値候補の単体テスト。"""
from akiya_watcher.alerts import (
    decide,
    looks_land_only,
    looks_ruin,
    offer_candidate_reason,
)
from akiya_watcher.models import Listing, ListingContext, Score
from akiya_watcher.storage import Diff


def make(**kw) -> Listing:
    base = dict(source="t", listing_id="1", title="テスト物件", url="u")
    base.update(kw)
    return Listing(**base)


def diff_of(ls, kind="new", **ctx_kw) -> Diff:
    ctx = ListingContext(current_price_yen=ls.price_yen, **ctx_kw)
    return Diff(kind=kind, listing=ls, context=ctx)


def score_of(total: int) -> Score:
    s = Score()
    s.total = total
    return s


# ---------------------------------------------------------------- 判定ヘルパー

def test_land_only_detection():
    assert looks_land_only(make(title="売地 山林300坪", description="更地渡し"))
    # 建物情報があれば土地系ワードが混ざっても建物付き扱い
    assert not looks_land_only(
        make(title="古家付き売地", layout="4DK", description="残置物あり"))
    assert not looks_land_only(make(title="普通の中古住宅", layout="4DK"))


def test_house_with_forest_is_not_land_only():
    """実際に誤判定した鹿屋市の物件: 山林付きの家は土地のみではない。"""
    ls = make(title="空き家バンク【売買】230万円 鹿児島県鹿屋市永野田町　家庭菜園可"
                    "　山林・３ＤＫ旧宅・物置・駐車場２台付き５ＤＫ平屋　水洗トイレ")
    assert not looks_land_only(ls)


def test_ruin_detection():
    assert looks_ruin(make(description="倒壊の恐れあり"))
    assert not looks_ruin(make(description="要リフォーム・残置物あり"))


# ---------------------------------------------------------------- 通知ゲート

def test_price_drop_always_notifies():
    ls = make(price_yen=1_000_000, layout="4DK")
    d = diff_of(ls, kind="changed", is_new=False, price_changed=True,
                previous_price_yen=3_000_000)
    dec = decide(d, score_of(3), min_score=8)   # 低スコアでも値下げは鳴る
    assert dec.notify and dec.kind == "drop"


def test_new_listing_needs_min_score():
    ls = make(price_yen=1_500_000, layout="4DK")
    assert decide(diff_of(ls), score_of(10), min_score=8).notify
    assert not decide(diff_of(ls), score_of(5), min_score=8).notify


def test_land_only_never_notifies():
    ls = make(title="山林 売地", description="更地")
    d = diff_of(ls, kind="changed", is_new=False, price_changed=True,
                previous_price_yen=3_000_000)
    ls.price_yen = 1_000_000
    d.context.current_price_yen = 1_000_000
    assert not decide(d, score_of(20), min_score=8).notify


def test_ruin_raises_threshold():
    ls = make(price_yen=500_000, layout="4DK", description="倒壊の恐れあり")
    # 通常なら8点で鳴るが、倒壊記載は+5されるため12点では鳴らない
    assert not decide(diff_of(ls), score_of(12), min_score=8, ruin_extra=5).notify
    assert decide(diff_of(ls), score_of(13), min_score=8, ruin_extra=5).notify


def test_change_without_drop_is_silent():
    ls = make(price_yen=1_500_000, layout="4DK")
    d = diff_of(ls, kind="changed", is_new=False, price_changed=False)
    assert not decide(d, score_of(20), min_score=8).notify


# ---------------------------------------------------------------- 指値候補

def test_offer_candidate_by_age():
    ls = make(price_yen=2_000_000, layout="4DK")
    d = diff_of(ls, kind="unchanged", is_new=False, age_days=120)
    assert "掲載120日" in offer_candidate_reason(d, min_age_days=90)


def test_offer_candidate_by_drop_history():
    ls = make(price_yen=1_000_000, layout="4DK")
    d = diff_of(ls, kind="unchanged", is_new=False, age_days=30,
                previous_price_yen=3_000_000)
    assert "値下げ履歴▼67%" in offer_candidate_reason(d, min_age_days=90)


def test_fresh_listing_is_not_offer_candidate():
    ls = make(price_yen=2_000_000, layout="4DK")
    d = diff_of(ls, kind="new", age_days=0)
    assert offer_candidate_reason(d) is None


def test_land_only_is_not_offer_candidate():
    ls = make(title="山林 売地")
    d = diff_of(ls, kind="unchanged", is_new=False, age_days=365)
    assert offer_candidate_reason(d) is None
