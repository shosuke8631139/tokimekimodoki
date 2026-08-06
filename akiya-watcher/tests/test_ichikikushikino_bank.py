"""いちき串木野市公式一覧とアットホーム一覧の統合テスト。"""
from akiya_watcher.models import Listing
from akiya_watcher.scrapers.ichikikushikino_bank import IchikikushikinoBankScraper

OFFICIAL = """
<table><tbody>
<tr><th>タイトル</th><th>地区</th><th>建築年</th><th>建築面積</th><th>区分</th><th>金額</th><th>担当</th><th>PDF</th></tr>
<tr><td><a href="https://ichikikushikino-c46219.akiya-athome.jp/bukken/detail/buy/135">空き家物件No.135</a></td><td>本浦</td><td>昭和40年</td><td>84</td><td>売買</td><td>準備中</td><td>業者 0996-00-0000</td><td><a href="/files/135.pdf">資料</a></td></tr>
<tr><td><a href="https://ichikikushikino-c46219.akiya-athome.jp/bukken/detail/buy/134/">空き家物件No.134</a></td><td>中央</td><td>昭和49年</td><td>50</td><td>売買</td><td>250万円</td><td>業者 0996-00-0000</td><td><a href="/files/134.pdf">資料</a></td></tr>
<tr><td>空き家物件No.132</td><td>野平</td><td>平成5年</td><td>103</td><td>売買</td><td>成約</td><td>業者 0996-00-0000</td><td></td></tr>
<tr><td>空き家物件No.140</td><td>羽島</td><td>昭和50年</td><td>90</td><td>売買</td><td>200万円</td><td>業者 0996-00-0000</td><td><a href="/files/140.pdf">資料</a></td></tr>
<tr><td>空き家物件No.129</td><td>照島</td><td>平成18年</td><td>122</td><td>賃貸</td><td>月7.5万円</td><td>業者</td><td></td></tr>
</tbody></table>
"""


def make_scraper() -> IchikikushikinoBankScraper:
    return IchikikushikinoBankScraper({
        "id": "ichikikushikino_akiya_bank",
        "official_url": "https://www.city.ichikikushikino.lg.jp/official.html",
        "list_url": "https://example.com/list",
        "item_selector": "li",
        "fields": {},
    })


def test_parse_official_table_ignores_rental_and_reads_status():
    records = make_scraper().parse_official(OFFICIAL)
    assert [record.number for record in records] == ["135", "134", "132", "140"]
    assert records[0].price_yen is None and records[0].status == "準備中"
    assert records[1].price_yen == 2_500_000
    assert records[2].sold
    assert records[3].floor_area_sqm == 90.0


def test_merge_keeps_athome_item_and_adds_only_missing_official_items():
    scraper = make_scraper()
    athome = [Listing(
        source="ichikikushikino_akiya_bank",
        listing_id="existing-134",
        title="中央の家",
        url="https://ichikikushikino-c46219.akiya-athome.jp/bukken/detail/buy/134",
        price_yen=2_600_000,
        address="鹿児島県いちき串木野市中央",
    )]
    merged = scraper.merge_listings(athome, scraper.parse_official(OFFICIAL))

    assert [listing.listing_id for listing in merged] == [
        "existing-134", "city-135", "city-140"]
    assert merged[0].price_yen == 2_500_000  # 市公式価格を優先
    assert merged[0].floor_area_sqm == 50.0
    assert "市公式No.134" in merged[0].description
    assert merged[1].price_yen is None and "準備中" in merged[1].title
    assert merged[2].price_yen == 2_000_000
    assert all("0996-00-0000" not in str(listing.raw) for listing in merged)


def test_preview_price_unknown_is_not_removed_by_unknown_price_filter():
    assert make_scraper().prices_reliable is False
