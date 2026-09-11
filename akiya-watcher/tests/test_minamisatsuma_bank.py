"""南さつま市 空き家バンクアダプタのテスト。"""
from akiya_watcher.models import Listing
from akiya_watcher.scrapers.minamisatsuma_bank import MinamisatsumaBankScraper

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>空き家情報（加世田一覧） - 南さつま市</title></head>
<body>
<table>
  <tr><th>登録番号</th><td><a href="/living/sumai-tochi/akiyabank/akiya-kaseda/e044073.html">103</a></td></tr>
  <tr><th>所在地</th><td>加世田内山田8222番地1</td></tr>
  <tr><th>建物</th><td>構造：木造、床面積：68.73㎡、建築年：昭和17年</td></tr>
  <tr><th>土地</th><td>土地面積：219.00㎡</td></tr>
  <tr><th>価格</th><td>●売却：700万円</td></tr>
  <tr><th>不動産業者</th><td>テスト不動産</td></tr>
</table>

<table>
  <tr><th>登録番号</th><td>176</td></tr>
  <tr><th>所在地</th><td>加世田11559番地</td></tr>
  <tr><th>建物</th><td>構造：木造、床面積：99.17㎡、建築年：昭和34年</td></tr>
  <tr><th>土地</th><td>土地面積：300.00㎡</td></tr>
  <tr><th>価格</th><td>●売却：50万円</td></tr>
  <tr><th>不動産業者</th><td>南さつま商事</td></tr>
</table>

<!-- 賃貸のみの物件 (売買価格に誤認しないことの検証) -->
<table>
  <tr><th>登録番号</th><td>999</td></tr>
  <tr><th>所在地</th><td>加世田本町1-1</td></tr>
  <tr><th>建物</th><td>床面積：50.00㎡</td></tr>
  <tr><th>土地</th><td>土地面積：100.00㎡</td></tr>
  <tr><th>価格</th><td>●賃貸：3万円/月</td></tr>
  <tr><th>不動産業者</th><td>賃貸不動産</td></tr>
</table>

<!-- 売買と賃貸の併記物件 (売却価格のみ抽出することの検証) -->
<table>
  <tr><th>登録番号</th><td>888</td></tr>
  <tr><th>所在地</th><td>加世田川畑100</td></tr>
  <tr><th>建物</th><td>床面積：80.00㎡</td></tr>
  <tr><th>土地</th><td>土地面積：250.00㎡</td></tr>
  <tr><th>価格</th><td>●売却：200万円　●賃貸：4万円/月</td></tr>
  <tr><th>不動産業者</th><td>合同不動産</td></tr>
</table>
</body>
</html>
"""

def test_parse_minamisatsuma_bank_listings():
    page_url = "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-itiran/e016252.html"
    listings = MinamisatsumaBankScraper.parse_page(SAMPLE_HTML, page_url)
    assert len(listings) == 4

    # 1. 通常物件 (詳細リンクあり)
    l103 = listings[0]
    assert l103.listing_id == "minamisatsuma-103"
    assert l103.title == "南さつま市空き家バンク No.103（加世田）"
    assert l103.price_yen == 7_000_000
    assert l103.address == "鹿児島県南さつま市加世田内山田8222番地1"
    assert l103.floor_area_sqm == 68.73
    assert l103.land_area_sqm == 219.00
    assert l103.url == "https://www.city.minamisatsuma.lg.jp/living/sumai-tochi/akiyabank/akiya-kaseda/e044073.html"

    # 2. 格安物件 (詳細リンクなし・アンカーフォールバック)
    l176 = listings[1]
    assert l176.listing_id == "minamisatsuma-176"
    assert l176.price_yen == 500_000
    assert l176.url == f"{page_url}#no-176"

    # 3. 賃貸のみ物件 (売買価格は None であり、3万円と誤認しないこと)
    l999 = listings[2]
    assert l999.listing_id == "minamisatsuma-999"
    assert l999.price_yen is None

    # 4. 売買・賃貸併記物件 (売却価格200万円が抽出され、賃料4万円と誤認しないこと)
    l888 = listings[3]
    assert l888.listing_id == "minamisatsuma-888"
    assert l888.price_yen == 2_000_000

def test_scraper_config_initialization():
    cfg = {"id": "minamisatsuma_akiya_bank"}
    scraper = MinamisatsumaBankScraper(cfg)
    assert scraper.source_id == "minamisatsuma_akiya_bank"
    assert scraper.full_snapshot is True
    assert scraper.prices_reliable is True
    assert len(scraper.list_urls) == 5
