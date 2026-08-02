"""generic_html の複数ページ対応(list_urls)のテスト。出水の2ページ読みで使用。"""
from unittest.mock import patch

from akiya_watcher.scrapers.generic_html import GenericHtmlScraper


PAGE1 = """
<ul class="property-list-one"><li>
  <dl><dt><a href="/bukken/detail/buy/x-1">売戸建住宅【1】</a></dt>
  <dd class="detail-info"><ul class="one-info">
    <li data-column="address"><span>鹿児島県 出水市高尾野町</span></li>
  </ul></dd></dl>
  <table class="room-list"><tbody><tr>
    <td class="price-strong" data-column="price"><span>430</span><span>万円</span></td>
    <td data-column="madori"><b>4LDK</b></td>
    <td data-column="menseki"><span>500㎡</span></td>
  </tr></tbody></table>
</li></ul>
"""

PAGE2 = PAGE1.replace("x-1", "x-2").replace("【1】", "【2】").replace("430", "50")


class _Res:
    def __init__(self, text):
        self.text = text


def test_複数ページを連結して読める():
    scraper = GenericHtmlScraper({
        "id": "izumi_test",
        "list_urls": ["https://example.com/list", "https://example.com/list?page=2"],
        "item_selector": "ul.property-list-one > li",
        "fields": {
            "title": {"selector": "dt a", "attr": "text"},
            "url": {"selector": "dt a", "attr": "href"},
            "price": {"selector": "td.price-strong", "attr": "text"},
            "address": {"selector": 'li[data-column="address"]', "attr": "text"},
        },
    })
    pages = {"https://example.com/list": PAGE1,
             "https://example.com/list?page=2": PAGE2}
    with patch.object(GenericHtmlScraper, "get",
                      lambda self, url, **kw: _Res(pages[url])):
        listings = scraper.fetch_listings()
    assert len(listings) == 2
    assert listings[0].price_yen == 4_300_000   # "430 万円" (spanの間の空白)
    assert listings[1].price_yen == 500_000
    assert listings[0].url == "https://example.com/bukken/detail/buy/x-1"
    assert "出水市" in listings[0].address


def test_単一list_urlも従来どおり動く():
    scraper = GenericHtmlScraper({
        "id": "single", "list_url": "https://example.com/list",
        "item_selector": "ul.property-list-one > li",
        "fields": {"title": {"selector": "dt a", "attr": "text"}},
    })
    with patch.object(GenericHtmlScraper, "get",
                      lambda self, url, **kw: _Res(PAGE1)):
        assert len(scraper.fetch_listings()) == 1
