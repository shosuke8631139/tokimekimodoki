"""都城市 空き家バンク(住めば住むほど都城)アダプタのテスト。"""
from akiya_watcher.scrapers.miyakonojo_bank import MiyakonojoBankScraper

INDEX = """
<html><body>
<a href="https://www.sumeba-sumuhodo-miyakonojo.jp/residence/%E3%80%90%E7%AE%A1%E7%90%86%E7%95%AA%E5%8F%B7421%E3%80%91%E5%A3%B2%E8%B2%B7%EF%BC%88%E8%93%91%E5%8E%9F%E7%94%BA%EF%BC%89/">物件A</a>
<a href="https://www.sumeba-sumuhodo-miyakonojo.jp/residence/【管理番号420】売買（松元町）/">物件B</a>
<a href="https://www.sumeba-sumuhodo-miyakonojo.jp/residence/【管理番号418】売買-土地（下長飯町）/">土地</a>
<a href="https://www.sumeba-sumuhodo-miyakonojo.jp/residence/【管理番号399】賃貸（山田町）/">賃貸</a>
<a href="https://www.sumeba-sumuhodo-miyakonojo.jp/residence/【管理番号421】売買（蓑原町）/">重複</a>
<a href="https://www.sumeba-sumuhodo-miyakonojo.jp/residence/">一覧へ戻る</a>
</body></html>
"""

DETAIL = """
<html><body>
<form><select><option>100万円以上</option><option>500万円以上</option></select></form>
<h1>【管理番号421】売買（蓑原町）</h1>
<table>
<tr><td>価格</td><td>250万円</td></tr>
<tr><td>間取り</td><td>5DK</td></tr>
<tr><td>築年数</td><td>築45年</td></tr>
<tr><td>備考</td><td>残置物あり。現状渡し。スーパーまで800m。</td></tr>
</table>
</body></html>
"""


def test_一覧から売買のみ重複なしで読める():
    items = MiyakonojoBankScraper.parse_index(INDEX)
    numbers = [n for n, _, _ in items]
    assert numbers == ["421", "420"]      # 土地・賃貸・重複・一覧リンクは除外
    number, place, url = items[0]
    assert place == "蓑原町"
    assert url.startswith("https://www.sumeba-sumuhodo-miyakonojo.jp/residence/")


def test_詳細から価格と説明が読める():
    price, desc = MiyakonojoBankScraper.parse_detail(DETAIL)
    assert price == 2_500_000
    assert "残置物あり" in desc
    assert "スーパーまで800m" in desc
    assert "100万円以上" not in desc      # 検索フォームの選択肢は混ざらない


def test_検索フォームの万円は価格として誤読しない():
    html = "<form><option>100万円以上</option></form><p>価格は応相談です</p>"
    price, _ = MiyakonojoBankScraper.parse_detail(html)
    assert price is None


def test_エンドツーエンド(monkeypatch):
    pages = {"https://example.com/list": INDEX}

    class _Res:
        def __init__(self, text):
            self.text = text
            self.encoding = "utf-8"

    def fake_get(self, url):
        return _Res(pages.get(url, DETAIL))

    monkeypatch.setattr(MiyakonojoBankScraper, "get", fake_get)
    scraper = MiyakonojoBankScraper({"id": "miyakonojo_sumeba",
                                     "list_url": "https://example.com/list"})
    listings = scraper.fetch_listings()
    assert len(listings) == 2
    l = listings[0]
    assert l.listing_id == "miyakonojo-421"
    assert l.address == "宮崎県都城市蓑原町"
    assert l.price_yen == 2_500_000
    assert "都城市空き家バンク No.421（蓑原町）【売買】" == l.title
