"""周辺情報の掘り出し(nearby_line)と地図リンクのテスト。"""
from akiya_watcher.models import Listing, ListingContext, Score
from akiya_watcher.notify import format_message
from akiya_watcher.storage import Diff
from akiya_watcher.travel import map_link, nearby_line


def test_距離つきの周辺情報を拾う():
    line = nearby_line("閑静な住宅地。スーパーまで500m、小学校まで徒歩10分。")
    assert "スーパーまで500m" in line
    assert "小学校まで徒歩10分" in line


def test_アットホーム系の交通欄を拾う():
    line = nearby_line("JR日豊本線 帖佐駅 / 車13分 築76年 1階建")
    assert "帖佐駅 車13分" in line


def test_市役所までの距離表記を拾う():
    line = nearby_line("貸戸建住宅 /6K 162㎡ (専有) 伊佐市大口小木原 市役所まで5.3ｋｍ")
    assert "市役所まで5.3km" in line


def test_距離なしの言及は控えめに拾う():
    line = nearby_line("スーパー近くで生活便利。")
    assert line == "周辺: スーパー近く"


def test_同じ施設は重複させず最大4件まで():
    line = nearby_line("スーパーまで500m。スーパーまで800m。小学校まで1km。"
                       "病院まで2km。役場まで3km。郵便局まで4km。")
    assert line.count("スーパー") == 1
    assert line.count("・") <= 3          # 最大4項目


def test_周辺情報がなければ行ごと出さない():
    assert nearby_line("静かな環境の平屋です。") is None
    assert nearby_line(None) is None


def test_地図リンクは住所をエンコードして作る():
    link = map_link("鹿児島県薩摩郡さつま町山崎")
    assert link.startswith("地図: https://www.google.com/maps/search/?api=1&query=")
    assert "%E9%B9%BF%E5%85%90%E5%B3%B6" in link   # 「鹿児島」がURLエンコードされる
    assert map_link(None) is None


def test_通知メールに周辺と地図の行が入る():
    ls = Listing(source="demo", listing_id="n", title="周辺情報つきの家",
                 url="https://example.com/n", price_yen=1_000_000,
                 address="鹿児島県姶良市住吉",
                 description="スーパーまで500m。JR日豊本線 帖佐駅 / 車13分。")
    text = format_message(
        Diff(kind="new", listing=ls,
             context=ListingContext(current_price_yen=1_000_000)),
        Score(total=10))
    assert "周辺: " in text
    assert "地図: https://www.google.com/maps" in text
    # 並び順: 所在地 → 立地 → 周辺 → 仕入れ点 → 地図
    assert (text.index("所在地") < text.index("立地:") < text.index("周辺:")
            < text.index("仕入れ点") < text.index("地図:"))
