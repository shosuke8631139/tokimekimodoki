"""パーサ・スコアラーの単体テスト。 pytest で実行。"""
import pytest

from akiya_watcher.criteria import (
    Scorer,
    assess_zanchi,
    is_flush_toilet,
    parse_area_sqm,
    parse_layout_rooms,
    parse_parking_slots,
    parse_price_yen,
)
from akiya_watcher.models import Listing, ListingContext


@pytest.mark.parametrize("text,expected", [
    ("198万円", 1_980_000),
    ("１９８万円", 1_980_000),
    ("1,980,000円", 1_980_000),
    ("200万", 2_000_000),
    ("1億2,000万円", 120_000_000),
    ("0円", 0),
    ("無償譲渡", 0),
    ("1,000円", 1_000),
    ("応相談", None),
    ("", None),
])
def test_parse_price(text, expected):
    assert parse_price_yen(text) == expected


def test_zero_yen_listing_scored_with_badge():
    ls = make(price_yen=0, layout="4DK", description="無償譲渡・残置物あり")
    s = Scorer(CRITERIA).score(ls)
    assert "💴0円" in s.badges


def test_out_of_ten_scale():
    from akiya_watcher.models import Score
    s = Score()
    s.total = 29
    assert s.out_of_ten == 10
    s.total = 15
    assert s.out_of_ten == 5
    s.total = -3
    assert s.out_of_ten == 0
    s.total = 99
    assert s.out_of_ten == 10  # 上限は10


@pytest.mark.parametrize("text,expected", [
    ("103.5㎡", 103.5),
    ("延床120m2", 120.0),
    ("80平米", 80.0),
    ("1,033㎡", 1033.0),
    ("不明", None),
])
def test_parse_area(text, expected):
    assert parse_area_sqm(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("4LDK", 4),
    ("5DK+S", 5),
    ("３ＬＤＫ", 3),
    ("ワンルーム", None),
])
def test_parse_layout(text, expected):
    assert parse_layout_rooms(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("駐車場:3台可", 3),
    ("駐車2台", 2),
    ("並列2台可", 2),
    ("カースペース2台分あり", 2),
    ("駐車場あり", 1),
    ("駐車場なし", None),
    ("", None),
])
def test_parse_parking(text, expected):
    assert parse_parking_slots(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("水洗(浄化槽)", True),
    ("公共下水", True),
    ("汲み取り式", False),
    ("簡易水洗", False),
    ("", None),
    ("記載なし", None),
])
def test_toilet(text, expected):
    assert is_flush_toilet(text) is expected


# ---------------------------------------------------------------- Scorer

CRITERIA = {"priority_cities": ["薩摩川内市", "鹿屋市", "出水市", "都城市"]}


def make(**kw) -> Listing:
    base = dict(source="t", listing_id="1", title="テスト物件", url="u")
    base.update(kw)
    return Listing(**base)


def test_nothing_is_excluded():
    """どんな物件でもスコアが付き、除外されない(思想の回帰テスト)。"""
    terrible = make(price_yen=9_000_000, toilet="汲み取り式",
                    floor_area_sqm=40.0, layout="2K")
    s = Scorer(CRITERIA).score(terrible)
    assert s.total is not None  # 例外も除外もなくスコアが返る


def test_price_drop_dominates():
    """大幅値下げは最重要シグナル。300万→100万のケース。"""
    ls = make(price_yen=1_000_000, address="鹿児島県薩摩川内市")
    ctx = ListingContext(is_new=False, age_days=20,
                         previous_price_yen=3_000_000,
                         current_price_yen=1_000_000, price_changed=True)
    s = Scorer(CRITERIA).score(ls, ctx)
    assert ctx.drop_pct == 67
    assert any("値下げ67%" in b for b in s.badges)
    assert s.total >= 10  # 値下げ6 + 100万以下4 + エリア1


def test_zanchibutsu_outweighs_bad_toilet():
    """残置物豊富なら汲み取り減点があってもプラス圏に残る。"""
    ls = make(price_yen=1_500_000, toilet="汲み取り式",
              description="残置物多数・家財あり・現状渡し")
    s = Scorer(CRITERIA).score(ls, ListingContext(is_new=False))
    assert "🪑残置物" in s.badges
    assert "⚠️汲み取り" in s.badges
    assert s.total > 0


@pytest.mark.parametrize("description,status", [
    ("残置物は現況のまま引渡し", "confirmed"),
    ("残置物有り。買主にて処分してください", "confirmed"),
    ("買主にて残置物を処分してください", "confirmed"),
    ("家財道具が残っています", "present"),
    ("現状有姿での引渡し", "as_is"),
    ("残置物は売主負担で処分", "removal"),
    ("売主にて残置物を撤去します", "removal"),
    ("家財・キッチン設備撤去済み", "removal"),
    ("残置物なし", "removal"),
    ("残置物無。", "removal"),
    ("きれいな空き家です", "none"),
])
def test_残置物と引渡し条件を意味で分類する(description, status):
    assert assess_zanchi(make(description=description)).status == status


def test_売主撤去は残置物候補として加点しない():
    s = Scorer(CRITERIA).score(
        make(price_yen=1_500_000, description="残置物は売主負担で処分します"),
        ListingContext(is_new=False),
    )
    assert "🪑残置物" not in s.badges
    assert "🧹残置物撤去" in s.badges


def test_現状有姿だけなら残置物確定にしない():
    s = Scorer(CRITERIA).score(
        make(price_yen=1_500_000, description="現状有姿で引渡します"),
        ListingContext(is_new=False),
    )
    assert "📦現状有姿" in s.badges
    assert "🪑残置物" not in s.badges
    assert "残置物の有無・処分条件" in s.unknowns


def test_motive_keywords_detected():
    ls = make(price_yen=2_500_000,
              description="相続のため売却。所有者は遠方在住で早期処分希望。")
    s = Scorer(CRITERIA).score(ls)
    assert "🏠売主事情" in s.badges
    assert "相続" in s.matched_keywords


def test_unknowns_are_kept_not_dropped():
    """情報ゼロの物件も落とさず、要確認リストが付く。"""
    ls = make()
    s = Scorer(CRITERIA).score(ls)
    assert "価格(応相談? 指値候補)" in s.unknowns
    assert "駐車場" in s.unknowns
    assert "トイレ形式" in s.unknowns


def test_parking_scale():
    five = Scorer(CRITERIA).score(make(parking_slots=5), ListingContext(is_new=False))
    two = Scorer(CRITERIA).score(make(parking_slots=2), ListingContext(is_new=False))
    one = Scorer(CRITERIA).score(make(parking_slots=1), ListingContext(is_new=False))
    assert five.total > two.total > one.total


def test_convenience_scored():
    ls = make(description="スーパー徒歩5分、小学校近く")
    s = Scorer(CRITERIA).score(ls)
    assert "🏪利便" in s.badges


def test_long_listing_bonus():
    ls = make(price_yen=2_000_000)
    old = Scorer(CRITERIA).score(ls, ListingContext(is_new=False, age_days=200))
    fresh = Scorer(CRITERIA).score(ls, ListingContext(is_new=False, age_days=10))
    assert old.total > fresh.total
    assert any("⏳" in b for b in old.badges)
