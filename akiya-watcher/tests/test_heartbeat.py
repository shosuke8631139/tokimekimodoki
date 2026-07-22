"""生存報告(何もない日の1日1回メール)のテスト。"""
from akiya_watcher.main import build_heartbeat, jst_today
from akiya_watcher.models import Listing, ListingContext, Score
from akiya_watcher.storage import Diff, Store


def _item(title: str, total: int, price: int | None = 1_000_000):
    ls = Listing(source="demo", listing_id=title, title=title,
                 url=f"https://example.com/{title}", price_yen=price)
    score = Score(total=total)
    return Diff(kind="new", listing=ls,
                context=ListingContext(current_price_yen=price)), score


def test_生存報告に注目上位が点数順で載る():
    items = [_item("ふつうの家", 3), _item("蔵のある家", 15), _item("安い家", 8)]
    text = build_heartbeat(items)
    assert "巡回は動いています" in text
    assert text.index("蔵のある家") < text.index("安い家") < text.index("ふつうの家")
    assert "https://example.com/蔵のある家" in text


def test_生存報告は上位5件まで():
    items = [_item(f"家{i}", i) for i in range(8)]
    text = build_heartbeat(items, top_n=5)
    assert text.count("https://example.com/") == 5


def test_監視ゼロ件でも壊れず注意を促す():
    text = build_heartbeat([])
    assert "0件" in text


def test_メタ記録で1日1回を判定できる(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.get_meta("last_mail_date") is None
    store.set_meta("last_mail_date", "2026-07-22")
    assert store.get_meta("last_mail_date") == "2026-07-22"
    store.set_meta("last_mail_date", "2026-07-23")  # 上書き
    assert store.get_meta("last_mail_date") == "2026-07-23"
    store.close()


def test_日本時間の日付が返る():
    assert len(jst_today()) == 10  # YYYY-MM-DD
