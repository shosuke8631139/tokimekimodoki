"""薩摩川内市 市直営CGIバンクのアダプタテスト。

実サイトで確認した一覧の型 (2026-08-03):
  .entry-list-box 内のリンク文字列に「管理番号/所在地/売買 ◯◯万」が入る。
"""
from akiya_watcher.scrapers.satsumasendai_city import SatsumasendaiCityScraper

BASE = "https://www.city.satsumasendai.lg.jp/cgi-bin/recruit.php/3/list"

HTML = """
<html><body>
<div class="entry-list-box">
  <span class="entry-list-tag">交渉中</span>
  <a href="/cgi-bin/recruit.php/3/detail/106?ck=1">
    08004/薩摩川内市樋脇町市比野1321-1/売買 100万</a>
</div>
<div class="entry-list-box">
  <a href="/cgi-bin/recruit.php/3/detail/107?ck=1">
    08005/薩摩川内市鹿島町藺牟田212-2/賃貸1万円、売買50万円</a>
</div>
<div class="entry-list-box">
  <a href="/cgi-bin/recruit.php/3/detail/74?ck=1">
    06007/薩摩川内市入来町浦之名149/賃貸 月額40,000円</a>
</div>
<div class="entry-list-box">
  <a href="/cgi-bin/recruit.php/3/detail/99?ck=1">
    交渉中 07022/薩摩川内市入来町浦之名3451/売買 770万円</a>
</div>
</body></html>
"""

HTML_PAGED = HTML.replace(
    "</body>",
    '<a href="/cgi-bin/recruit.php/3/list?page_no=2">次へ</a></body>')


def test_parse_index_sales_only():
    items, next_url = SatsumasendaiCityScraper.parse_index(HTML, BASE)
    assert next_url is None
    # 賃貸のみ(06007)は落ち、売買3件が残る
    assert [ls.raw["number"] for ls in items] == ["08004", "08005", "07022"]
    a = items[0]
    assert a.price_yen == 1_000_000
    assert a.address == "鹿児島県薩摩川内市樋脇町市比野1321-1"
    assert "No.08004" in a.title and "交渉中" in a.title
    assert a.url.startswith("https://www.city.satsumasendai.lg.jp/")
    # 「賃貸1万円、売買50万円」は売買側の50万を読む
    assert items[1].price_yen == 500_000
    assert items[2].price_yen == 7_700_000


def test_parse_index_pagination_link():
    _, next_url = SatsumasendaiCityScraper.parse_index(HTML_PAGED, BASE)
    assert next_url == \
        "https://www.city.satsumasendai.lg.jp/cgi-bin/recruit.php/3/list?page_no=2"


def test_price_gate_design():
    # 売買価格が読めない物件を台帳に入れない設計 (応相談カットが効く)
    assert SatsumasendaiCityScraper.prices_reliable is True
    assert SatsumasendaiCityScraper.full_snapshot is True
