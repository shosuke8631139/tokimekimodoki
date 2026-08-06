"""日置市 市直営バンク(地域別ページ)のアダプタテスト。

実サイトで確認した型 (2026-08-03):
  表の行 = 物件番号(詳細リンク) | 建物情報など | お問い合わせ先。
  価格は円建て。「値下げ！」で新旧2価格が並ぶ。詳細URLに bukken/bukkenn の
  表記ゆれあり。
"""
from akiya_watcher.scrapers.hioki_bank import HiokiBankScraper

BASE = ("https://www.city.hioki.kagoshima.jp/teiju/ijuteju/akiya/"
        "akiyabank/akiyabank_fukiage.html")

HTML = """
<html><head><title>吹上地域（伊作、花田、野首）｜鹿児島県日置市</title></head>
<body>
<table>
<tr><th>物件番号</th><th>建物情報など</th><th>お問い合わせ先</th></tr>
<tr>
  <td><a href="/teiju/bukkenn103.html">103</a></td>
  <td>値下げ！ 木造平屋建て、蔵付き 建物：32.55坪、土地：120坪
      売却希望価格：2,000,000円 → 1,500,000円</td>
  <td>担当業者：有限会社松山不動産 電話：099-296-XXXX</td>
</tr>
<tr>
  <td><a href="/teiju/bukken266.html">266</a></td>
  <td>木造平屋建て 建物：30坪、土地：178.03坪 売却希望価格：3,000,000円</td>
  <td>担当業者：有限会社郡山木材建設</td>
</tr>
<tr>
  <td><a href="/teiju/bukken387.html">387</a></td>
  <td>賃貸値下げ！ (賃貸ペット可) 木造平屋建て 賃貸希望価格：月額30,000円</td>
  <td>担当業者：有限会社郡山木材建設</td>
</tr>
</table>
</body></html>
"""


def test_parse_page():
    items = HiokiBankScraper.parse_page(HTML, BASE)
    # 賃貸のみ(387・30,000円は売却規模未満)は落ち、売却2件が残る
    assert [ls.raw["number"] for ls in items] == ["103", "266"]

    kura = items[0]
    assert kura.price_yen == 1_500_000                      # 値下げ後
    assert kura.advertised_previous_price_yen == 2_000_000  # 値下げ前
    assert kura.address == "鹿児島県日置市吹上町"           # 地域→町名
    assert "蔵付き" in kura.description                     # 仕入れ点の材料
    assert kura.url.endswith("/teiju/bukkenn103.html")      # 表記ゆれURLもそのまま

    plain = items[1]
    assert plain.price_yen == 3_000_000
    assert plain.advertised_previous_price_yen is None


def test_design_flags():
    assert HiokiBankScraper.prices_reliable is True
    assert HiokiBankScraper.full_snapshot is True


def test_parse_detail_price_reads_current_and_previous_yen_prices():
    html = """
    <main><h2>希望価格</h2><p>2,000,000円<br>5,000,000円</p>
    <h2>建築時期</h2><p>昭和55年</p></main>
    """
    assert HiokiBankScraper.parse_detail_price(html) == (2_000_000, 5_000_000)


def test_detail_price_fills_stale_list_but_does_not_undo_newer_list_drop():
    items = HiokiBankScraper.parse_page(HTML, BASE)
    listing = items[1]

    # 詳細の方が新しい例: 一覧300万円、詳細200万円→500万円
    HiokiBankScraper.merge_detail_price(listing, 2_000_000, 5_000_000)
    assert listing.price_yen == 2_000_000
    assert listing.advertised_previous_price_yen == 5_000_000

    # 一覧の方がさらに新しい例: 一覧100万円→旧150万円、詳細は150万円→旧450万円
    listing.price_yen = 1_000_000
    listing.advertised_previous_price_yen = 1_500_000
    HiokiBankScraper.merge_detail_price(listing, 1_500_000, 4_500_000)
    assert listing.price_yen == 1_000_000
    assert listing.advertised_previous_price_yen == 1_500_000
