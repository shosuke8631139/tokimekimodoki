"""追跡リスト(指名物件ウォッチ)のテスト。ネットワークは使わない。"""
from akiya_watcher.scrapers.watch import WatchScraper, parse_watch_page

SAMPLE = """<html><head>
<title>空き家バンク【売買】300万円 鹿児島県伊佐市大口牛尾 吹抜け・ステンドグラス有 5DK2階建 - Sumai空き家</title>
<meta property="og:title" content="空き家バンク【売買】300万円 鹿児島県伊佐市大口牛尾 吹抜け・ステンドグラス有 5DK2階建 - Sumai空き家" />
</head><body>
物件種別 売買（建物・土地） 売買価格 300万円 物件所在地 鹿児島県伊佐市大口牛尾
建物-構造 木造2階建 建物-間取 5DK 土地-面積 282.02㎡ 駐車場 有 各階水洗トイレ
空き家になった時期 令和6年
</body></html>"""


def test_指名物件ページを読み取れる():
    ls = parse_watch_page("https://akiya.sumai.biz/117604", SAMPLE)
    assert ls is not None
    assert ls.source == "watch"
    assert ls.listing_id == "117604"
    assert ls.title.startswith("⭐追跡:")
    assert ls.price_yen == 3_000_000
    assert "伊佐市" in ls.address
    assert "水洗" in ls.description


def test_成約表示のページは掲載終了扱いでNoneになる():
    html = ("<html><head><title>お知らせ - Sumai空き家</title></head>"
            "<body>この物件は成約しました。掲載を終了しています。</body></html>")
    assert parse_watch_page("https://akiya.sumai.biz/1", html) is None


def test_指名物件は常にキープで足切り免除のフラグを持つ():
    s = WatchScraper({"id": "watchlist", "entries": []})
    assert s.always_keep is True
    assert s.full_snapshot is True   # リストから消えたら掲載終了として検知
    assert s.prices_reliable is False


def test_エントリが空なら何も返さない():
    s = WatchScraper({"id": "watchlist", "entries": [{"url": ""}]})
    assert s.fetch_listings() == []
