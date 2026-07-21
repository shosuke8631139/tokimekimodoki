"""アットホーム空き家バンク共通システムの解析テスト (実採取HTMLに基づく)。"""
from unittest.mock import patch

from akiya_watcher.scrapers.generic_html import GenericHtmlScraper

# 2026-07 に鹿児島市サイトから採取した実構造 (賃貸1件を加えて除外を検証)
SAMPLE_HTML = """
<ul class="property-simple">
<li>
 <div class="property-name"><a href="/bukken/detail/buy/x-47542">西佐多町（No.14）</a></div>
 <dl class="bukken-info">
  <dt>価格</dt>
  <dd class="price-strong"><span>500</span><span></span><span>万円</span></dd>
  <dd>売戸建住宅 /<b>6DK</b></dd>
  <dd><span class="view-strong">425.78㎡</span>(土地) / <span class="view-strong">63.65㎡</span>(延床)</dd>
  <dd><span class="smp-display-none">鹿児島県</span>鹿児島市西佐多町</dd>
  <dd>バス 吉田中バス停 停歩3分</dd>
 </dl>
</li>
<li>
 <div class="property-name"><a href="/bukken/detail/rent/y-99">賃貸の部屋</a></div>
 <dl class="bukken-info">
  <dt>価格</dt>
  <dd class="price-strong"><span>3</span><span></span><span>万円</span></dd>
  <dd>賃貸住宅 /<b>2DK</b></dd>
  <dd><span class="view-strong">40㎡</span>(延床)</dd>
  <dd><span class="smp-display-none">鹿児島県</span>鹿児島市中央町</dd>
  <dd>徒歩5分</dd>
 </dl>
</li>
</ul>
"""

CONFIG = {
    "id": "kagoshima_city_akiya_bank",
    "list_url": "https://kagoshima-c46201.akiya-athome.jp/",
    "item_selector": "ul.property-simple > li",
    "must_include": "売",
    "fields": {
        "title": {"selector": ".property-name a", "attr": "text"},
        "url": {"selector": ".property-name a", "attr": "href"},
        "price": {"selector": "dl.bukken-info dd.price-strong", "attr": "text"},
        "layout": {"selector": "dl.bukken-info dd:nth-of-type(2)", "attr": "text"},
        "land_area": {"selector": "dl.bukken-info dd:nth-of-type(3)", "attr": "text"},
        "address": {"selector": "dl.bukken-info dd:nth-of-type(4)", "attr": "text"},
        "description": {"selector": "dl.bukken-info", "attr": "text"},
    },
}


class FakeResponse:
    text = SAMPLE_HTML


def test_akiya_athome_bank_parsing():
    scraper = GenericHtmlScraper(CONFIG)
    with patch.object(scraper, "get", return_value=FakeResponse()):
        listings = scraper.fetch_listings()

    assert len(listings) == 1  # 賃貸は must_include: "売" で除外される
    ls = listings[0]
    assert ls.title == "西佐多町（No.14）"
    assert ls.url == "https://kagoshima-c46201.akiya-athome.jp/bukken/detail/buy/x-47542"
    assert ls.price_yen == 5_000_000
    assert "鹿児島市西佐多町" in ls.address
    assert ls.land_area_sqm == 425.78      # 最初の面積 = 土地
    assert "6DK" in ls.layout