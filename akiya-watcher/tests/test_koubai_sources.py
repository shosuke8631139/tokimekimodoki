"""公売・県有財産アダプタ (KSI・国税庁・鹿児島県) の解析テスト。

実サイトで確認した構造 (2026-08-09 Actions run 31315520891 / 31315669435)
を模したHTMLで、ネットワークなしに解析ロジックを検証する。
"""
from akiya_watcher.scrapers.ksi_auction import KsiAuctionScraper
from akiya_watcher.scrapers.nta_koubai import NtaKoubaiScraper
from akiya_watcher.scrapers.pref_kagoshima_sale import PrefKagoshimaSaleScraper

# ---------------------------------------------------------------- KSI

KSI_HTML = """
<html><body>
<div class="space-y-4">
  <div><a href="/items/69238/">入札終了</a>
    <a href="/items/69238/">鹿児島県薩摩川内市青山町　宅地１区画ほか【広々敷地】</a></div>
  <div><span>物件価格</span><span>500,000</span><span>円</span>
    <span>インターネット公売</span>
    <span>所在地</span><span>青山町１２３番地</span>
    <span>カテゴリ</span><span>土地</span>
    <span>間取り</span><span>-</span></div>
</div>
<div class="space-y-4">
  <div><a href="/items/69722/">入札中</a>
    <a href="/items/69722/">【苗場スキー場近く】越後湯沢のリゾートマンション</a></div>
  <div><span>物件価格</span><span>195,000</span><span>円</span>
    <span>所在地</span><span>南魚沼郡湯沢町大字三国３１９番地７</span>
    <span>カテゴリ</span><span>区分所有建物</span>
    <span>間取り</span><span>1DK</span></div>
</div>
</body></html>
"""

BASE = "https://kankocho.jp/search/real-estate/"


def test_ksi_parse_excludes_closed_by_default():
    items = KsiAuctionScraper.parse_list(KSI_HTML, BASE)
    # 入札終了の鹿児島物件は落ち、入札中の1件だけ残る
    assert [ls.listing_id for ls in items] == ["69722"]
    ls = items[0]
    assert ls.price_yen == 195_000
    assert ls.layout == "1DK"
    assert ls.url == "https://kankocho.jp/items/69722/"
    # 所在地に県名が無いためタイトルを併記してエリア判定に使える形にする
    assert "南魚沼郡湯沢町" in ls.address and "越後湯沢" in ls.address


def test_ksi_parse_include_closed_for_recon():
    items = KsiAuctionScraper.parse_list(KSI_HTML, BASE, include_closed=True)
    assert [ls.listing_id for ls in items] == ["69238", "69722"]
    kago = items[0]
    assert kago.price_yen == 500_000
    assert "薩摩川内市" in kago.address   # target_areas マッチが通る
    assert kago.raw["status"] == "入札終了"


KSI_WAITING_HTML = """
<html><body>
<div class="space-y-4">
  <div><a href="/items/70303/">入札開始待ち</a>
    <a href="/items/70303/">宮城県登米市津山町　土地付建物</a></div>
  <div><span>物件価格</span><span>845,000</span><span>円</span>
    <span>所在地</span><span>登米市津山町柳津字黄牛宇名173番4</span>
    <span>カテゴリ</span><span>土地付建物</span>
    <span>間取り</span><span>-</span></div>
</div>
</body></html>
"""


def test_ksi_waiting_status_is_not_title():
    # 「入札開始待ち」は状態ラベル。タイトルに化けさせない (2026-08-09 実地で発見)
    items = KsiAuctionScraper.parse_list(KSI_WAITING_HTML, BASE)
    assert len(items) == 1
    assert items[0].title == "宮城県登米市津山町　土地付建物"
    assert items[0].raw["status"] == "入札開始待ち"


def test_ksi_flags():
    # 1頁目しか読まないため「消えた=売れた」と誤記録しない設計
    assert KsiAuctionScraper.full_snapshot is False


# ---------------------------------------------------------------- 国税庁

NTA_HTML = """
<html><body>
<table>
  <tr>
    <td>鹿児島県霧島市国分中央１２３番</td>
    <td>熊本国税局</td><td>1,234,000円</td><td>期間入札</td>
    <td><a href="hp0201.php?kyoku_no=08001&koubai_nendo=2026&baikyaku_no=100">
      詳細を見る</a></td>
  </tr>
  <tr>
    <td><a href="hp0201.php?os=8001&doc=7">宮城県仙台市青葉区　農地</a></td>
    <td>仙台国税局</td><td>567,000円</td>
  </tr>
</table>
</body></html>
"""

NTA_BASE = "https://www.koubai.nta.go.jp/auctionx/public/hp0241.php?pageid=0"


def test_nta_parse_rows():
    items = NtaKoubaiScraper.parse_list(NTA_HTML, NTA_BASE)
    assert len(items) == 2
    a = items[0]
    assert a.price_yen == 1_234_000
    assert a.address.startswith("鹿児島県霧島市")
    # リンクが「詳細を見る」ボタンの行は住所からタイトルを組み立てる
    assert a.title.startswith("公売物件 鹿児島県霧島市")
    assert a.url.startswith("https://www.koubai.nta.go.jp/auctionx/public/hp0201.php")
    b = items[1]
    assert b.listing_id == "os8001"
    assert b.title == "宮城県仙台市青葉区　農地"
    assert b.address.startswith("宮城県仙台市")


def test_nta_flags():
    # 一覧行からの推定読みのため、価格Noneを応相談カットさせない
    assert NtaKoubaiScraper.prices_reliable is False
    assert NtaKoubaiScraper.full_snapshot is False


# ---------------------------------------------------------------- 鹿児島県

PREF_HTML = """
<html><body>
<ul>
  <li><a href="/ab06/kensei/nyusatu/zaisan/bukenholder/kyuutaiseiryou.html">
    物件明細（旧大成寮）</a></li>
  <li><a href="/ab06/kensei/nyusatu/zaisan/bukenholder/keisatsu.html">
    物件明細（旧姶良警察署（庁舎）跡地）</a></li>
  <li><a href="/kensei/nyusatu/zaisan/bukken/index.html">売却中の物件明細</a></li>
  <li><a href="/kensei/nyusatu/zaisan/yotei/index.html">今後売却予定の物件明細</a></li>
  <li><a href="/kensei/nyusatu/index.html">入札情報・資格審査</a></li>
</ul>
</body></html>
"""

PREF_BASE = "https://www.pref.kagoshima.jp/kensei/nyusatu/zaisan/bukken/index.html"


def test_pref_parse_index():
    items = PrefKagoshimaSaleScraper.parse_index(PREF_HTML, PREF_BASE)
    # 物件明細だけ。案内リンク(index.html)やナビは拾わない
    assert len(items) == 2
    a = items[0]
    assert a.title == "県有財産売却: 旧大成寮"
    assert a.url.startswith("https://www.pref.kagoshima.jp/ab06/")
    assert a.price_yen is None
    # 入れ子括弧の物件名も欠けずに読む (2026-08-09 実地で発見)
    assert items[1].title == "県有財産売却: 旧姶良警察署（庁舎）跡地"


def test_pref_flags():
    # 売却中の全物件一覧なので、消えた = 売れた/取り下げの検知に使う
    assert PrefKagoshimaSaleScraper.full_snapshot is True
    assert PrefKagoshimaSaleScraper.prices_reliable is False
