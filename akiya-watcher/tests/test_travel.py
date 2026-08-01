"""立地の即席分析(自宅=国分からの車の所要時間)のテスト。"""
from akiya_watcher.notify import format_message
from akiya_watcher.models import Listing, ListingContext, Score
from akiya_watcher.storage import Diff
from akiya_watcher.travel import drive_minutes, location_line, zone_label


def test_国分は本命圏():
    mins = drive_minutes("鹿児島県霧島市国分中央3丁目")
    assert mins is not None and mins <= 35
    assert zone_label(mins) == "◎30分圏"


def test_さつま町は60分圏あたり():
    mins = drive_minutes("鹿児島県薩摩郡さつま町山崎")
    assert 40 <= mins <= 80   # 概算なので幅を持たせる


def test_出水や宮崎市は圏外表示():
    assert zone_label(drive_minutes("鹿児島県出水市境町")) == "△圏外(参考)"
    assert zone_label(drive_minutes("宮崎県宮崎市大塚町")) == "△圏外(参考)"


def test_霧島市は地区で精度が変わる():
    # 横川(市北部)は国分より遠い判定になる
    assert drive_minutes("霧島市横川町") > drive_minutes("霧島市国分府中")


def test_地名不明はNone():
    assert drive_minutes(None) is None
    assert drive_minutes("東京都千代田区") is None
    assert location_line("東京都千代田区") is None


def test_通知メッセージに立地行が入る():
    ls = Listing(source="demo", listing_id="t", title="さつま町の家",
                 url="https://example.com/t", price_yen=500_000,
                 address="鹿児島県薩摩郡さつま町宮之城")
    text = format_message(Diff(kind="new", listing=ls,
                               context=ListingContext(current_price_yen=500_000)),
                          Score(total=10))
    assert "立地: 国分から車およそ" in text
    assert text.index("所在地") < text.index("立地")


def test_住所不明の物件では立地行が出ない():
    ls = Listing(source="demo", listing_id="t2", title="住所不明の家",
                 url="https://example.com/t2", price_yen=500_000)
    text = format_message(Diff(kind="new", listing=ls,
                               context=ListingContext(current_price_yen=500_000)),
                          Score(total=10))
    assert "立地:" not in text
