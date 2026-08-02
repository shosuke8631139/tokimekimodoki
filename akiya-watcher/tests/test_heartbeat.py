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
    assert "本日の定期便" in text
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


def test_通知が出た日の定期便は別送済みの案内になる():
    text = build_heartbeat([], notified=2)
    assert "別メールでお知らせ済み" in text
    assert "2件" in text


def test_初登場には新マーク_既出には既出マーク():
    items = [_item("常連の家", 15), _item("新顔の家", 12)]
    prev = {items[0][0].listing.uid}          # 常連だけ前回紹介済み
    text = build_heartbeat(items, prev_uids=prev)
    assert "🆕 " in text and "新顔の家" in text
    assert "（既出）" in text
    # マークの対応が正しい (新顔に🆕、常連に既出)。物件の箇条書き行だけ見る
    for line in text.splitlines():
        if not line.startswith("・"):
            continue
        if "新顔の家" in line:
            assert "🆕" in line and "既出" not in line
        if "常連の家" in line:
            assert "既出" in line and "🆕" not in line


def test_全員既出なら一覧を畳んで1行にする():
    items = [_item("常連A", 15), _item("常連B", 12)]
    prev = {d.listing.uid for d, _ in items}
    text = build_heartbeat(items, prev_uids=prev)
    assert "前回と同じ顔ぶれ" in text
    assert "https://example.com/常連A" not in text   # 一覧は出さない


def test_初回はマークなしで従来どおり():
    items = [_item("初日の家", 15)]
    text = build_heartbeat(items)                    # prev_uids なし
    assert "🆕" not in text and "既出" not in text
    assert "初日の家" in text
