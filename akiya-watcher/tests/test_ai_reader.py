"""仕入れ点(売主の困り気配)採点エンジンのテスト。卒業制作フェーズ1。"""
from akiya_watcher.ai_reader import read_listing
from akiya_watcher.models import Listing, ListingContext
from akiya_watcher.notify import format_message
from akiya_watcher.storage import Diff
from akiya_watcher.models import Score


def _ls(desc: str, title: str = "テスト物件") -> Listing:
    return Listing(source="demo", listing_id="t", title=title,
                   url="https://example.com/t", price_yen=1_000_000,
                   description=desc)


def test_困り気配が濃い物件は高得点で理由つき():
    r = read_listing(_ls("相続のため売却。家財道具が残ったままの現状渡し。"
                         "遠方在住のため管理できず、早めに手放したいです。"))
    assert r.score >= 60
    assert "残置物ごと引渡しが明確" in r.reasons
    assert "相続の気配" in r.reasons
    assert "遠方管理の気配" in r.reasons


def test_手入れ済み物件は減点される():
    plain = read_listing(_ls("戸建て住宅です。"))
    reformed = read_listing(_ls("戸建て住宅です。リフォーム済み。"))
    assert reformed.score < plain.score or reformed.score == 0
    assert any("手入れ済み" in x for x in reformed.reasons)


def test_値下げ履歴と長期掲載で加点される():
    ctx = ListingContext(current_price_yen=1_000_000,
                         previous_price_yen=4_000_000,  # ▼75%
                         age_days=200)
    r = read_listing(_ls("戸建て住宅です。"), ctx)
    assert any("値下げ履歴▼75%" in x for x in r.reasons)
    assert any("長期掲載200日" in x for x in r.reasons)
    assert r.score >= 30


def test_点数は0から100に収まる():
    ctx = ListingContext(current_price_yen=100_000,
                         previous_price_yen=4_000_000, age_days=999)
    r = read_listing(_ls("相続 実家 残置物 現状渡し 遠方 早め 処分 蔵 納屋 倉庫"), ctx)
    assert 0 <= r.score <= 100
    assert read_listing(_ls("リフォーム済のきれいな家")).score >= 0


def test_理由は強い順に並ぶ():
    r = read_listing(_ls("残置物あり。蔵つき。"))
    assert r.reasons[0] == "残置物あり(処分条件要確認)"   # 20点が10点より先


def test_通知メールに仕入れ点の行が入る():
    ls = _ls("相続のため残置物ごと現状渡し。", title="気配の濃い家")
    text = format_message(
        Diff(kind="new", listing=ls,
             context=ListingContext(current_price_yen=1_000_000)),
        Score(total=10))
    assert "仕入れ点: " in text
    assert "残置物ごと引渡しが明確" in text
    assert "残置物判定: A 確定" in text


def test_売主撤去は残置物加点にならない():
    r = read_listing(_ls("残置物は売主負担で処分します。"))
    assert "残置物ごと引渡しが明確" not in r.reasons
    assert "残置物あり(処分条件要確認)" not in r.reasons
    assert any("売主撤去" in reason for reason in r.reasons)


def test_気配ゼロでも壊れない():
    r = read_listing(_ls(""))
    assert r.score == 0
    assert "特筆する気配なし" in r.line
