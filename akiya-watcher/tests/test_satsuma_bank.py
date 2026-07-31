"""さつま町空き家バンクアダプタのテスト。

フィクスチャは 2026-07 に GitHub Actions で取得した実HTMLの構造を縮約したもの
(h2見出し + a.pdf + div.wysiwyg がフラットに並ぶ)。
"""
from akiya_watcher.scrapers.satsuma_bank import SatsumaBankScraper

FIXTURE = """
<div>
 <h2><span class="bg"><span class="bg2"><span class="bg3">空き家の購入を考えてらっしゃる方へ</span></span></span></h2>
 <div class="wysiwyg"><p>こちらのページは空き家情報バンクに登録している物件（売買）一覧です。</p></div>

 <h2><span class="bg"><span class="bg2"><span class="bg3">No.186 【売買】</span></span></span></h2>
 <p class="file-link-item"><a class="pdf" href="//www.satsuma-net.jp/material/files/group/14/No186r.pdf">No.186 (PDFファイル: 770.8KB)</a></p>
 <figure class="img-item"><img alt="" src="//example/186.jpg"/></figure>
 <div class="wysiwyg">
  <p>場所：柏原</p>
  <p>売買：390万円</p>
  <p>問い合わせ：株式会社左近允（0996-29-5798）</p>
  <p>備考：町の中心部に近く、日当たり良好で閑静な場所です。</p>
 </div>

 <h2><span class="bg"><span class="bg2"><span class="bg3">No.163 【売買】</span></span></span></h2>
 <p class="file-link-item"><a class="pdf" href="//www.satsuma-net.jp/material/files/group/14/No163R.pdf">No.163 (PDFファイル: 689.2KB)</a></p>
 <div class="wysiwyg">
  <p>場所：虎居</p>
  <p>売買： <strong class="text_">200万円</strong> （2025年6月2日、380万円から変更。)</p>
  <p>問い合わせ：白石商事（0996-53-1775）</p>
  <p>備考：さつま町役場（本庁）・病院・商業施設にも近い住宅地です。</p>
 </div>

 <h2><span class="bg"><span class="bg2"><span class="bg3">NO.106【売買】</span></span></span></h2>
 <p class="file-link-item"><a class="pdf" href="//www.satsuma-net.jp/material/files/group/14/No106.pdf">NO.106 (PDF)</a></p>
 <div class="wysiwyg">
  <p>場所：宮之城屋地</p>
  <p>価格： <strong>600万円</strong> （2024年7月23日、700万円から変更。)</p>
  <p>問い合わせ：白石商事（0996-53-1775）</p>
  <p>備考：町の中心部に位置し、役場本庁まで徒歩3分程度です。</p>
 </div>
</div>
"""


def make_scraper() -> SatsumaBankScraper:
    return SatsumaBankScraper({
        "id": "satsuma_akiya_bank",
        "list_url": "https://www.satsuma-net.jp/teiju/akiya/1/5623.html",
    })


def test_parse_count_and_ids():
    listings = make_scraper().parse(FIXTURE)
    assert [l.listing_id for l in listings] == ["satsuma-186", "satsuma-163", "satsuma-106"]


def test_plain_price_listing():
    l = make_scraper().parse(FIXTURE)[0]
    assert l.price_yen == 3_900_000
    assert l.advertised_previous_price_yen is None
    assert l.address == "鹿児島県薩摩郡さつま町柏原"
    assert l.url == "https://www.satsuma-net.jp/material/files/group/14/No186r.pdf"
    assert "左近允" in l.description


def test_discounted_listing_keeps_previous_price():
    l = make_scraper().parse(FIXTURE)[1]
    assert l.price_yen == 2_000_000
    assert l.advertised_previous_price_yen == 3_800_000
    assert "虎居" in l.title


def test_kakaku_label_variant():
    """「売買：」ではなく「価格：」表記の物件も読める。"""
    l = make_scraper().parse(FIXTURE)[2]
    assert l.price_yen == 6_000_000
    assert l.advertised_previous_price_yen == 7_000_000


def test_target_area_filter_accepts_satsuma_address():
    """収集フィルタ(target_areas: さつま町)が住所で通ることの確認。"""
    l = make_scraper().parse(FIXTURE)[0]
    assert "さつま町" in l.address
