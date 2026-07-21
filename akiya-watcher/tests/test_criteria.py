"""判定・パーサの単体テスト。 pytest で実行。"""
import pytest

from akiya_watcher.criteria import (
    Judge,
    is_flush_toilet,
    parse_area_sqm,
    parse_layout_rooms,
    parse_parking_slots,
    parse_price_yen,
)
from akiya_watcher.models import Listing


@pytest.mark.parametrize("text,expected", [
    ("198万円", 1_980_000),
    ("１９８万円", 1_980_000),
    ("1,980,000円", 1_980_000),
    ("200万", 2_000_000),
    ("1億2,000万円", 120_000_000),
    ("応相談", None),
    ("", None),
])
def test_parse_price(text, expected):
    assert parse_price_yen(text) == expected


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


CRITERIA = {
    "price_max_yen": 2_000_000,
    "parking_min_slots": 2,
    "floor_area_min_sqm": 80,
    "rooms_min": 4,
    "require_flush_toilet": True,
    "priority_cities": ["鹿児島市"],
}


def make(**kw) -> Listing:
    base = dict(source="t", listing_id="1", title="テスト物件", url="u")
    base.update(kw)
    return Listing(**base)


def test_judge_ideal_listing_matches():
    ls = make(price_yen=1_800_000, floor_area_sqm=98.0, layout="5DK",
              parking_slots=3, toilet="水洗(浄化槽)",
              address="鹿児島県鹿児島市", description="残置物あり・現状渡し")
    j = Judge(CRITERIA).judge(ls)
    assert j.matched
    assert "残置物" in j.matched_keywords
    assert "現状渡し" in j.matched_keywords
    assert j.score >= 6


def test_judge_price_over_disqualifies():
    ls = make(price_yen=3_000_000, floor_area_sqm=120.0,
              parking_slots=2, toilet="水洗")
    j = Judge(CRITERIA).judge(ls)
    assert not j.matched
    assert any("上限超過" in d for d in j.disqualifiers)


def test_judge_kumitori_disqualifies_when_required():
    ls = make(price_yen=1_000_000, floor_area_sqm=90.0,
              parking_slots=2, toilet="汲み取り式")
    assert not Judge(CRITERIA).judge(ls).matched
    relaxed = dict(CRITERIA, require_flush_toilet=False)
    assert Judge(relaxed).judge(ls).matched


def test_judge_land_area_fallback_for_parking():
    ls = make(price_yen=1_500_000, floor_area_sqm=85.0,
              land_area_sqm=250.0, toilet="水洗")
    j = Judge(CRITERIA).judge(ls)
    assert j.matched
    assert any("駐車余地" in r for r in j.reasons)


def test_judge_parking_parsed_from_description():
    ls = make(price_yen=1_500_000, floor_area_sqm=85.0, toilet="水洗",
              description="駐車場:2台あり。残置物あり。")
    j = Judge(CRITERIA).judge(ls)
    assert j.matched


def test_judge_small_house_disqualifies():
    ls = make(price_yen=1_000_000, floor_area_sqm=60.0, layout="3K",
              parking_slots=2, toilet="水洗")
    assert not Judge(CRITERIA).judge(ls).matched


def test_judge_unknown_price_stays_candidate():
    ls = make(price_yen=None, floor_area_sqm=90.0,
              parking_slots=2, toilet="水洗")
    j = Judge(CRITERIA).judge(ls)
    assert j.matched
    assert any("価格不明" in r for r in j.reasons)
