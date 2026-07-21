"""商談ノート(実戦データ)のテスト。"""
from akiya_watcher.criteria import Scorer
from akiya_watcher.models import Listing
from akiya_watcher.report import render_report
from akiya_watcher.storage import DEAL_STATUSES, Store


def make(i: str, **kw) -> Listing:
    base = dict(source="t", listing_id=i, title=f"物件{i}", url=f"u{i}",
                price_yen=1_500_000, layout="4DK")
    base.update(kw)
    return Listing(**base)


def test_deal_lifecycle(tmp_path):
    store = Store(tmp_path / "db.sqlite", now=0)
    ls = make("1", title="薩摩川内の家")
    store.upsert(ls)

    store.set_deal(ls.uid, "問い合わせ済", note="メール送付")
    store.set_deal(ls.uid, "指値中", offer_yen=1_000_000, note="100万で指した")
    store.set_deal(ls.uid, "見送り", offer_yen=1_000_000, note="断られた。130万なら可と言われた")

    deals = store.deals()
    assert deals[ls.uid]["status"] == "見送り"          # 最新状態
    hist = store.deal_history()
    assert len(hist) == 3                                # 履歴は全部残る
    assert hist[-1]["status"] == "問い合わせ済"
    assert hist[0]["note"] == "断られた。130万なら可と言われた"
    assert hist[0]["title"] == "薩摩川内の家"            # 物件情報と結合される
    store.close()


def test_recent_listings_excludes_delisted(tmp_path):
    store = Store(tmp_path / "db.sqlite", now=0)
    a, b = make("a"), make("b")
    store.upsert(a)
    store.upsert(b)
    store.finalize_crawl("t", {a.uid})   # b が消えた
    uids = [x["uid"] for x in store.recent_listings()]
    assert a.uid in uids and b.uid not in uids
    store.close()


def test_report_shows_deal_badge_and_history(tmp_path):
    store = Store(tmp_path / "db.sqlite", now=0)
    ls = make("1", title="商談中の家", description="残置物あり")
    diff = store.upsert(ls)
    store.set_deal(ls.uid, "指値中", offer_yen=1_000_000, note="返事待ち")

    score = Scorer({}).score(ls, diff.context)
    html = render_report([(diff, score)], deals=store.deals(),
                         deal_history=store.deal_history())
    assert "🤝指値中 100万" in html
    assert "実戦データ" in html
    assert "返事待ち" in html
    store.close()


def test_deal_statuses_defined():
    assert "指値中" in DEAL_STATUSES and "成約" in DEAL_STATUSES