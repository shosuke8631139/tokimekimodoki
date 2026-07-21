"""Sumai空き家アダプタのテスト。

タイトル解析は、ユーザーが実際に逃した霧島市物件の実タイトルを使って検証する。
"""
from akiya_watcher.criteria import Scorer
from akiya_watcher.models import Listing, ListingContext
from akiya_watcher.scrapers.sumai_akiya import parse_listing_title
from akiya_watcher.storage import Diff, Store

# 実物件のタイトル (スクリーンショットより)
REAL_TITLE = ("(価格変更)空き家バンク【売買】300万円→100万円 鹿児島県霧島市隼人町小浜"
              "　海水浴場近い・桜島を望む バルコニー・駐車場付き5SLDK平屋 水洗トイレ")


def test_parse_real_title():
    p = parse_listing_title(REAL_TITLE)
    assert p is not None
    assert p["price_yen"] == 1_000_000
    assert p["advertised_previous_price_yen"] == 3_000_000
    assert "鹿児島県霧島市隼人町小浜" in p["address"]


def test_parse_title_without_change():
    p = parse_listing_title("空き家バンク【売買】250万円 鹿児島県薩摩川内市 4DK 駐車2台")
    assert p["price_yen"] == 2_500_000
    assert p["advertised_previous_price_yen"] is None
    assert "薩摩川内市" in p["address"]


def test_non_listing_links_rejected():
    assert parse_listing_title("地域別") is None
    assert parse_listing_title("九州 (498)") is None
    assert parse_listing_title("当サイトの使い方") is None
    assert parse_listing_title("空き家バンク【賃貸】3万円 鹿児島県鹿屋市") is None


def test_advertised_drop_scores_on_first_sight(tmp_path):
    """初回取得でも「300万→100万」表記なら値下げバッジが付き通知対象になる。"""
    from akiya_watcher.alerts import decide
    p = parse_listing_title(REAL_TITLE)
    ls = Listing(source="sumai_akiya", listing_id="x1", title=p["title"],
                 url="https://akiya.sumai.biz/x", price_yen=p["price_yen"],
                 address=p["address"], description=p["title"],
                 advertised_previous_price_yen=p["advertised_previous_price_yen"])

    store = Store(tmp_path / "db.sqlite", now=0)
    diff = store.upsert(ls)
    # main.collect と同じ合成処理
    if ls.advertised_previous_price_yen and diff.context.previous_price_yen is None:
        diff.context.previous_price_yen = ls.advertised_previous_price_yen
        if diff.kind == "new":
            diff.context.price_changed = True

    assert diff.context.drop_pct == 67
    score = Scorer({"priority_cities": ["霧島市"]}).score(ls, diff.context)
    assert any("値下げ67%" in b for b in score.badges)
    assert "🚗" in " ".join(score.badges) or any("駐車" in r for r in score.reasons)

    dec = decide(diff, score, min_score=8)
    assert dec.notify and dec.kind == "drop"   # 逃した物件は、今度は鳴る
    store.close()
