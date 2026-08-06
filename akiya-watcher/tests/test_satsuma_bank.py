"""さつま町空き家バンクアダプタのテスト。

フィクスチャは 2026-07 に GitHub Actions で取得した実HTMLの構造を縮約したもの
(h2見出し + a.pdf + div.wysiwyg がフラットに並ぶ)。
"""
from akiya_watcher.models import Listing, Score
from akiya_watcher.notify import format_message
from akiya_watcher.scrapers.satsuma_bank import (
    SatsumaBankScraper,
    parse_pdf_details,
)
from akiya_watcher.storage import Diff
from akiya_watcher.models import ListingContext

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

 <h2><span class="bg"><span class="bg2"><span class="bg3">No.67【売買】</span></span></span></h2>
 <p class="file-link-item"><a class="pdf" href="//www.satsuma-net.jp/material/files/group/15/hp_yatitetsukasyou.pdf">No.67 (PDF)</a></p>
 <div class="wysiwyg">
  <p>場所：宮之城屋地 価格： 2,000万円 （R7.10月14日、2,500万円から変更） 問い合わせ：さつま町役場さつまPR課 備考：市街地中心部にあり、建物、敷地とも十分な広さがあります。</p>
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
    assert [l.listing_id for l in listings] == [
        "satsuma-186", "satsuma-163", "satsuma-106", "satsuma-67"]


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


def test_one_paragraph_variant():
    """全ラベルが1段落に詰め込まれた物件(実サイトNo.67の書式)も読める。"""
    l = make_scraper().parse(FIXTURE)[3]
    assert l.price_yen == 20_000_000
    assert l.advertised_previous_price_yen == 25_000_000
    assert l.address == "鹿児島県薩摩郡さつま町宮之城屋地"
    assert "宮之城屋地" in l.title and "問い合わせ" not in l.title


def test_parse_pdf_details_handles_split_labels_and_full_width_text():
    """PDFで項目名と値が改行されても、必要な4項目を読める。"""
    text = """
    間 取 り：６ＤＫ
    駐車場 有（普通車２台）
    土地\n面積：３２１．５０㎡
    延床\n面積：１２３．４㎡
    """
    assert parse_pdf_details(text) == {
        "layout": "6DK",
        "parking_slots": 2,
        "land_area_sqm": 321.5,
        "floor_area_sqm": 123.4,
    }


def test_parse_pdf_details_handles_real_satsuma_checkbox_form():
    """実サイトNo.185で確認した、チェック欄・部屋明細型の書式。"""
    text = (
        "間取り 1階 \uf052居間 \uf052台所 \uf052風呂 \uf052トイレ "
        "\uf052和室 6帖×2 4.5帖×1 \uf052板間 5帖×1 "
        "2階 ☐洋室 ☐和室 ☐トイレ "
        "建築面積（延床面積）73.55m2 建築時期 昭和27年築 "
        "駐車場 ☐有（約 台） \uf052無 庭 ☐有 \uf052無 "
        "敷地面積 138.8m2"
    )
    assert parse_pdf_details(text) == {
        "layout": "4室+台所",
        "parking_slots": 0,
        "land_area_sqm": 138.8,
        "floor_area_sqm": 73.55,
    }


def test_parse_pdf_details_handles_concatenated_room_counts():
    """pypdfが空白を落とした実サイトの「×24.5帖」「×12階」を分離する。"""
    text = (
        "間取り1階\uf052居間\uf052台所\uf052和室6帖×24.5帖×1"
        "\uf052板間5帖×12階☐洋室☐和室☐トイレ"
        "建築面積(延床面積)73.55m2"
    )
    assert parse_pdf_details(text)["layout"] == "4室+台所"


def test_apply_pdf_details_adds_email_line():
    listing = Listing(
        source="satsuma_akiya_bank",
        listing_id="satsuma-200",
        title="さつま町の架空物件",
        url="https://example.com/200.pdf",
        price_yen=2_000_000,
        address="鹿児島県薩摩郡さつま町",
    )
    make_scraper().apply_enrichment(listing, {
        "layout": "5DK",
        "parking_slots": 3,
        "land_area_sqm": 400.0,
        "floor_area_sqm": 110.5,
    })
    text = format_message(
        Diff("new", listing, ListingContext(is_new=True)), Score(total=10))
    assert "物件情報: 間取り 5DK / 駐車 3台 / 土地 400㎡ / 建物 110.5㎡" in text


def test_collect_reads_pdf_only_when_listing_changes(tmp_path, monkeypatch):
    """同じPDFを毎巡回読まず、価格変更時だけ読み直す。"""
    from akiya_watcher.main import collect

    price = {"yen": 2_000_000}
    pdf_fetches: list[int] = []

    def fake_fetch_listings(self):
        return [Listing(
            source=self.source_id,
            listing_id="satsuma-200",
            title="さつま町の架空物件",
            url="https://example.com/200.pdf",
            price_yen=price["yen"],
            address="鹿児島県薩摩郡さつま町",
        )]

    def fake_enrich(self, listing):
        pdf_fetches.append(listing.price_yen)
        return self.apply_enrichment(listing, {
            "layout": "5DK", "parking_slots": 2,
            "land_area_sqm": 350.0, "floor_area_sqm": 100.0,
        })

    monkeypatch.setattr(SatsumaBankScraper, "fetch_listings", fake_fetch_listings)
    monkeypatch.setattr(SatsumaBankScraper, "enrich_listing", fake_enrich)
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"max_price_yen": 3_000_000},
        "sources": [{
            "id": "satsuma_akiya_bank", "type": "satsuma_bank",
            "list_url": "https://example.com/list",
        }],
    }

    first, *_ = collect(config)
    second, *_ = collect(config)
    price["yen"] = 1_800_000
    third, *_ = collect(config)

    assert pdf_fetches == [2_000_000, 1_800_000]
    assert first[0][0].listing.parking_slots == 2
    assert second[0][0].listing.parking_slots == 2  # DBから復元
    assert third[0][0].context.price_changed
