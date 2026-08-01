"""霧島市空き家バンクアダプタのテスト。

フィクスチャは2026-07にGitHub Actionsで確認した実HTML構造の縮約
(table.datatable の th/td 行+直後の<ul>に登録カードPDF)。
"""
from akiya_watcher.scrapers.kirishima_bank import KirishimaBankScraper

FIXTURE = """
<div class="col_main">
 <p>各物件の内覧希望や価格等の詳細につきましては、空き家バンク登録カードに記載の仲介業者へ直接お問い合わせください。</p>

 <table border="1" class="datatable"><tbody>
  <tr><th><p>登録No</p></th><td><p>0284</p></td></tr>
  <tr><th>更新日</th><td><p>令和8年7月9日</p></td></tr>
  <tr><th><p>所在地</p></th><td><p>国分清水3丁目27-21</p></td></tr>
  <tr><th><p>種類</p></th><td><p>賃貸物件</p></td></tr>
  <tr><th><p>賃料</p></th><td><p>35,000円/月　敷金等70,000円</p></td></tr>
  <tr><th><p>その他</p></th><td><p>住宅街にありながら、比較的に閑静な物件</p></td></tr>
 </tbody></table>
 <div><ul>
  <li><a href="/documents/284.pdf">空き家バンク登録カード（№284）（PDF：253KB）</a></li>
  <li><a href="https://maps.example/284">物件の所在地（外部サイトへリンク）</a></li>
 </ul></div>

 <table border="1" class="datatable"><tbody>
  <tr><th><p>登録No</p></th><td><p>0271</p></td></tr>
  <tr><th><p>所在地</p></th><td><p>横川町中ノ272</p></td></tr>
  <tr><th><p>種類</p></th><td><p>売買物件</p></td></tr>
  <tr><th><p>価格</p></th><td><p>1,300万円</p></td></tr>
  <tr><th><p>その他</p></th><td><p>築100年以上の古民家物件です。</p></td></tr>
 </tbody></table>
 <div><ul>
  <li><a href="/documents/271.pdf">空き家バンク登録カード（No.271）（PDF：275KB）</a></li>
 </ul></div>

 <table border="1" class="datatable"><tbody>
  <tr><th><p>登録No</p></th><td><p>0268</p></td></tr>
  <tr><th><p>所在地</p></th><td><p>国分広瀬2丁目</p></td></tr>
  <tr><th><p>種類</p></th><td><p>売買物件</p></td></tr>
  <tr><th><p>価格</p></th><td><p>980万円</p></td></tr>
  <tr><th><p>その他</p></th><td><p>駐車スペースも5台以上可能な物件です。</p></td></tr>
 </tbody></table>
 <div><ul>
  <li><a href="/documents/268.pdf">空き家バンク登録カード（No.268）（PDF：231KB）</a></li>
 </ul></div>
</div>
"""

PAGE_URL = "https://www.city-kirishima.jp/kyodo/shise/ijuteju/akiya/akiyabankkokubu.html"


def make_scraper() -> KirishimaBankScraper:
    return KirishimaBankScraper({"id": "kirishima_akiya_bank", "list_urls": [PAGE_URL]})


def test_only_sales_listings_collected():
    listings = make_scraper().parse(FIXTURE, PAGE_URL)
    assert [l.listing_id for l in listings] == ["kirishima-0271", "kirishima-0268"]


def test_fields():
    l = make_scraper().parse(FIXTURE, PAGE_URL)[0]
    assert l.price_yen == 13_000_000
    assert l.address == "鹿児島県霧島市横川町中ノ272"
    assert l.url == "https://www.city-kirishima.jp/documents/271.pdf"
    assert "古民家" in l.description


def test_card_pdf_association_is_per_table():
    """2件目の物件には2件目のPDFが対応する(前後の取り違えがない)。"""
    l = make_scraper().parse(FIXTURE, PAGE_URL)[1]
    assert l.url.endswith("/documents/268.pdf")
    assert l.price_yen == 9_800_000
