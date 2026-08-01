"""湧水町 空家バンクアダプタのテスト (実サイト構造は2026-08に実地確認済み)。"""
from akiya_watcher.scrapers.yusui_bank import YusuiBankScraper

SAMPLE = """
<html><body>
<table><tbody><tr>
  <td><p><a href="#akibank">空家・空地バンクについて</a></p></td>
</tr></tbody></table>
<table><tbody>
<tr>
  <td style="text-align:center">
    <p><strong>No.250　売買２００万円</strong>［木場］</p>
    <p><a href="/soshiki/34/11308.html"><img alt="外観" src="/uploaded/image/5249.jpg"/></a></p>
  </td>
  <td style="text-align:center">
    <p><strong>No.248　売買450万円</strong>［恒次］</p>
    <p><a href="/soshiki/34/11307.html"><img alt="外観" src="/uploaded/image/5250.jpg"/></a></p>
  </td>
</tr>
<tr>
  <td>
    <p><strong>No.245 売買1,000万円</strong>［米永］</p>
    <p><a href="/soshiki/34/11105.html"><img alt="外観" src="/x.jpg"/></a></p>
  </td>
  <td>
    <p><strong>No.240 賃貸2万円/月</strong>［川添］</p>
    <p><a href="/soshiki/34/10937.html"><img alt="外観" src="/y.jpg"/></a></p>
  </td>
</tr>
<tr>
  <td>
    <p><strong>No.127</strong>［幸田］</p>
    <p><strong>売買1000万円</strong></p>
    <p><a href="/soshiki/34/8111.html"><img alt="外観" src="/z.jpg"/></a></p>
  </td>
  <td>
    <p><strong>No.169-3 売買300万円</strong>［北方］</p>
    <p><a href="/soshiki/34/9770.html"><img alt="外観" src="/w.jpg"/></a></p>
  </td>
</tr>
<tr>
  <td>
    <p><strong>No.232 売買応相談</strong>［般若寺］</p>
    <p><a href="/soshiki/34/10382.html"><img alt="外観" src="/v.jpg"/></a></p>
  </td>
  <td>
    <p><strong>No.92 売買応相談 賃貸3.5万円/月</strong>［田尾原］</p>
    <p><a href="/soshiki/34/4397.html"><img alt="外観" src="/u.jpg"/></a></p>
  </td>
</tr>
</tbody></table>
</body></html>
"""


def _scrape():
    scraper = YusuiBankScraper({
        "id": "yusui_akiya_bank",
        "list_url": "https://www.town.yusui.kagoshima.jp/soshiki/34/787.html",
    })
    return scraper.parse(SAMPLE)


def test_売買物件だけ読み取れる():
    listings = _scrape()
    ids = [l.listing_id for l in listings]
    assert "yusui-250" in ids
    assert "yusui-240" not in ids     # 賃貸のみは収集しない
    assert len(listings) == 7


def test_売買と賃貸の併記物件で賃貸額を誤読しない():
    by_id = {l.listing_id: l for l in _scrape()}
    assert by_id["yusui-92"].price_yen is None   # 売買は応相談 (3.5万円は賃貸額)


def test_全角数字とカンマの価格が読める():
    by_id = {l.listing_id: l for l in _scrape()}
    assert by_id["yusui-250"].price_yen == 2_000_000    # ２００万円 (全角)
    assert by_id["yusui-245"].price_yen == 10_000_000   # 1,000万円
    assert by_id["yusui-127"].price_yen == 10_000_000   # Noと価格が別strong
    assert by_id["yusui-232"].price_yen is None         # 応相談


def test_枝番と地区と詳細リンク():
    by_id = {l.listing_id: l for l in _scrape()}
    l = by_id["yusui-169-3"]
    assert "北方" in l.address
    assert l.address.startswith("鹿児島県姶良郡湧水町")
    assert l.url == "https://www.town.yusui.kagoshima.jp/soshiki/34/9770.html"
    assert "湧水町空家バンク No.169-3" in l.title


def test_ナビゲーションのtdは無視される():
    listings = _scrape()
    assert all("バンクについて" not in l.title for l in listings)
