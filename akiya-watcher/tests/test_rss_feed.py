"""RSSアダプタのテスト (実際のSumai空き家フィードの形式を再現)。"""
from unittest.mock import patch

from akiya_watcher.scrapers.rss_feed import RssScraper

FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Sumai 空き家</title>
<item>
  <title>空き家バンク【売買】230万円 鹿児島県鹿屋市永野田町　家庭菜園可　山林・３ＤＫ旧宅・物置・駐車場２台付き５ＤＫ平屋　水洗トイレ</title>
  <link>https://akiya.sumai.biz/kagoshima-kanoya-123?utm=rss</link>
  <pubDate>Mon, 20 Jul 2026 09:00:00 +0900</pubDate>
</item>
<item>
  <title>（価格変更）空き家バンク【売買】300万円→100万円 鹿児島県霧島市隼人町小浜　海水浴場近い・桜島を望む　バルコニー・駐車場付き５ＳＬＤＫ平屋　水洗トイレ</title>
  <link>https://akiya.sumai.biz/kagoshima-kirishima-456</link>
  <pubDate>Mon, 20 Jul 2026 08:00:00 +0900</pubDate>
</item>
<item>
  <title>長野県の空き家バンク</title>
  <link>https://akiya.sumai.biz/nagano-akiyabank</link>
</item>
</channel></rss>"""


class FakeResponse:
    content = FEED_XML.encode("utf-8")


def make_scraper():
    return RssScraper({"id": "sumai_test", "feed_urls": ["https://example.com/feed"]})


def test_rss_parses_listings_and_skips_non_listings():
    scraper = make_scraper()
    with patch.object(scraper, "get", return_value=FakeResponse()):
        listings = scraper.fetch_listings()
    assert len(listings) == 2  # 「長野県の空き家バンク」(目次記事)は物件でないので除外

    kanoya = next(l for l in listings if "鹿屋市" in l.address)
    assert kanoya.price_yen == 2_300_000
    assert kanoya.url == "https://akiya.sumai.biz/kagoshima-kanoya-123?utm=rss"


def test_rss_price_change_title_becomes_drop():
    """あの逃した霧島市物件と同形式のRSS投稿が、初見で値下げ扱いになる。"""
    scraper = make_scraper()
    with patch.object(scraper, "get", return_value=FakeResponse()):
        listings = scraper.fetch_listings()
    kirishima = next(l for l in listings if "霧島市" in l.address)
    assert kirishima.price_yen == 1_000_000
    assert kirishima.advertised_previous_price_yen == 3_000_000


def test_rss_dedupes_across_feeds():
    scraper = RssScraper({"id": "t", "feed_urls": ["u1", "u2"]})
    with patch.object(scraper, "get", return_value=FakeResponse()):
        listings = scraper.fetch_listings()
    assert len(listings) == 2  # 2フィードに同じ物件が出ても1件になる