"""メール解析アダプタの単体テスト。

実際のポータル通知メールを模したHTML/テキストメールから物件が抽出でき、
既存パイプライン(スコア・値下げ検知)に合流することを検証する。
"""
from email.message import EmailMessage

from akiya_watcher.criteria import Scorer
from akiya_watcher.scrapers.mailbox import extract_listings_from_email
from akiya_watcher.storage import Store


def html_mail(subject: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "info@example-portal.jp"
    msg.set_content("テキスト版は省略")
    msg.add_alternative(html, subtype="html")
    return msg


def text_mail(subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


PORTAL_HTML = """
<html><body>
<p>新着物件のお知らせ</p>
<table><tr><td>
  <a href="https://www.athome.co.jp/kodate/1234567890/?TRACKING=mail123">
    鹿児島県薩摩川内市 中古一戸建て
  </a>
  <br>価格: 180万円 / 5DK / 駐車3台
  <br>残置物あり・現状渡し。相続物件。
</td></tr>
<tr><td>
  <a href="https://suumo.jp/chukoikkodate/kagoshima/sc_kanoya/nc_98765/">
    鹿屋市 格安戸建て
  </a>
  <br>価格: 250万円
</td></tr>
<tr><td>
  <a href="https://www.example-portal.jp/unsubscribe">配信停止はこちら</a>
</td></tr>
</body></html>
"""


def test_extract_from_html_mail():
    listings = extract_listings_from_email(html_mail("【新着】2件", PORTAL_HTML))
    assert len(listings) == 2  # 配信停止リンクは対象ドメイン外なので無視
    athome = next(l for l in listings if l.source == "mail:アットホーム")
    assert athome.price_yen == 1_800_000
    assert "薩摩川内市" in athome.title
    assert "残置物" in athome.description
    suumo = next(l for l in listings if l.source == "mail:SUUMO")
    assert suumo.price_yen == 2_500_000


def test_extract_from_text_mail():
    body = """新着物件のお知らせ

■鹿児島県出水市 中古戸建て
価格: 150万円 家財残置・現状渡し
https://www.rakumachi.jp/syuuekibukken/area/dtl/999999/

以上"""
    listings = extract_listings_from_email(text_mail("楽待 新着", body))
    assert len(listings) == 1
    ls = listings[0]
    assert ls.source == "mail:楽待"
    assert ls.price_yen == 1_500_000
    assert "出水市" in ls.title
    assert "家財" in ls.description


def test_tracking_params_do_not_duplicate_listings():
    """トラッキングパラメータが違うだけの同一物件は同一IDになる。"""
    a = extract_listings_from_email(html_mail("mail1", PORTAL_HTML))
    html2 = PORTAL_HTML.replace("TRACKING=mail123", "TRACKING=mail999")
    b = extract_listings_from_email(html_mail("mail2", html2))
    ids_a = {l.uid for l in a}
    ids_b = {l.uid for l in b}
    assert ids_a == ids_b


def test_mail_listing_joins_scoring_and_drop_detection(tmp_path):
    """メール由来の物件も値下げ検知・スコアリングに乗る。"""
    store = Store(tmp_path / "db.sqlite", now=0)
    athome = next(l for l in extract_listings_from_email(html_mail("新着", PORTAL_HTML))
                  if l.source == "mail:アットホーム")
    diff = store.upsert(athome)
    assert diff.kind == "new"
    score = Scorer({"priority_cities": ["薩摩川内市"]}).score(athome, diff.context)
    assert "🪑残置物" in score.badges
    assert "🏠売主事情" in score.badges
    store.close()

    # お気に入り更新メールで価格が下がった想定 (同一URL・新価格)
    html_drop = PORTAL_HTML.replace("180万円", "100万円")
    store = Store(tmp_path / "db.sqlite", now=86400 * 10)
    athome2 = next(l for l in extract_listings_from_email(html_mail("価格更新", html_drop))
                   if l.source == "mail:アットホーム")
    diff = store.upsert(athome2)
    assert diff.context.previous_price_yen == 1_800_000
    assert diff.context.drop_pct == 44
    store.close()


def test_no_portal_links_returns_empty():
    msg = html_mail("関係ないメール", '<a href="https://example.com/x">リンク</a>')
    assert extract_listings_from_email(msg) == []


def test_junk_links_are_ignored():
    """実際のアットホームメールにある宣伝・案内リンクを物件と誤認しない。"""
    html = """
    <html><body>
    <a href="https://www.athome.co.jp/company/123/">掲載会社：(有)アート不動産</a>
    <a href="https://www.athome.co.jp/assess/">アットホーム売却査定</a>
    <a href="https://www.athome.co.jp/list/">★すべてのおすすめ物件をみる</a>
    <a href="https://www.athome.co.jp/detail/999/">詳しい物件情報はコチラ↓</a>
    <a href="https://www.athome.co.jp/mansion/">＜PR＞おすすめ新築マンション情報！！</a>
    <table><tr><td>
      <a href="https://www.athome.co.jp/kodate/555/">鹿児島県出水市 中古一戸建て</a>
      <br>150万円 4DK 残置物あり
    </td></tr></table>
    </body></html>
    """
    listings = extract_listings_from_email(html_mail("おすすめ物件", html))
    assert len(listings) == 1
    assert "出水市" in listings[0].title


def test_link_without_price_or_address_is_ignored():
    """価格も住所も無いリンクは物件行とみなさない。"""
    html = ('<div><a href="https://www.athome.co.jp/x/">売事務所</a></div>'
            '<div><a href="https://www.athome.co.jp/y/">鹿屋市の店舗</a> 250万円</div>')
    listings = extract_listings_from_email(html_mail("m", html))
    assert len(listings) == 1
    assert listings[0].price_yen == 2_500_000
