"""取得→スコア→差分→レポートのエンドツーエンドテスト。

シナリオ: 「300万円で掲載→3週間後に100万円へ値下げ」を再現し、
値下げの瞬間がレポートの『今すぐ確認』に上がることを検証する。
"""
import json

import yaml

from akiya_watcher.criteria import Scorer
from akiya_watcher.models import Listing
from akiya_watcher.report import render_report
from akiya_watcher.scrapers import build_scraper
from akiya_watcher.storage import Store

DAY = 86400


def _demo_rows(price="300万円"):
    return [{
        "id": "e2e-1",
        "title": "薩摩川内市 相続空き家",
        "url": "https://example.com/1",
        "price": price,
        "address": "鹿児島県薩摩川内市",
        "floor_area": "98㎡",
        "layout": "5DK",
        "parking": "駐車場:5台",
        "toilet": "水洗(浄化槽)",
        "description": "相続のため売却。残置物あり現状渡し。スーパー近く。",
    }]


def _fetch(tmp_path, rows):
    p = tmp_path / "demo.json"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    scraper = build_scraper({"id": "demo", "type": "demo", "path": str(p)})
    return scraper.fetch_listings()


def test_price_drop_scenario(tmp_path):
    db = tmp_path / "db.sqlite"
    scorer = Scorer({"priority_cities": ["薩摩川内市"]})

    # Day 0: 300万円で新規掲載
    store = Store(db, now=0)
    (ls,) = _fetch(tmp_path, _demo_rows("300万円"))
    diff = store.upsert(ls)
    assert diff.kind == "new" and diff.context.is_new
    store.close()

    # Day 21: 100万円へ値下げ → 値下げ67%が検知される
    store = Store(db, now=21 * DAY)
    (ls,) = _fetch(tmp_path, _demo_rows("100万円"))
    diff = store.upsert(ls)
    assert diff.kind == "changed"
    assert diff.context.price_changed
    assert diff.context.previous_price_yen == 3_000_000
    assert diff.context.drop_pct == 67
    assert diff.context.age_days == 21

    score = scorer.score(ls, diff.context)
    assert any("値下げ67%" in b for b in score.badges)

    # レポートの「今すぐ確認」に載る
    html = render_report([(diff, score)])
    assert "今すぐ自分の目で見る (1件)" in html
    assert "▼67%" in html
    assert "3,000,000円" in html and "1,000,000円" in html
    store.close()

    # Day 22: 変化なし → unchanged だが値下げバッジは履歴から維持される
    store = Store(db, now=22 * DAY)
    (ls,) = _fetch(tmp_path, _demo_rows("100万円"))
    diff = store.upsert(ls)
    assert diff.kind == "unchanged"
    assert not diff.context.price_changed
    assert diff.context.drop_pct == 67  # 履歴上の直前価格との比較は残る
    score = scorer.score(ls, diff.context)
    html = render_report([(diff, score)])
    assert "今すぐ自分の目で見る (0件)" in html  # 当日の値下げではないので緊急枠外
    store.close()


def test_report_ranks_by_score(tmp_path):
    scorer = Scorer({})
    store = Store(tmp_path / "db.sqlite", now=0)
    rows = [
        {"id": "a", "title": "残置物豊富な家", "url": "u1", "price": "150万円",
         "description": "残置物・家財あり現状渡し。相続物件。", "parking": "駐車3台"},
        {"id": "b", "title": "情報の少ない家", "url": "u2", "price": "600万円"},
    ]
    items = []
    for ls in _fetch(tmp_path, rows):
        diff = store.upsert(ls)
        items.append((diff, scorer.score(ls, diff.context)))
    html = render_report(items)
    assert html.index("残置物豊富な家") < html.index("情報の少ない家")
    assert "要確認" in html  # 情報のない物件も落とされず要確認つきで載る
    store.close()


def test_run_end_to_end(tmp_path, capsys):
    """main.run が収集→通知→レポート生成まで通ることを確認。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps(_demo_rows(), ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"priority_cities": ["薩摩川内市"]},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))
    out = capsys.readouterr().out
    assert "🆕 新着物件" in out
    assert report.exists()
    assert "物件台帳レポート" in report.read_text(encoding="utf-8")


def test_digest_mode(tmp_path, capsys):
    """--digest は個別通知の代わりに指値候補つきのまとめを送る。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps(_demo_rows(), ensure_ascii=False), encoding="utf-8")
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"priority_cities": ["薩摩川内市"]},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), digest=True)
    out = capsys.readouterr().out
    assert "📊 週次ダイジェスト" in out
    assert "🎯 指値候補" in out
    assert "🆕 新着物件" not in out  # 個別通知は出ない


def test_target_areas_scope(tmp_path, capsys):
    """リサーチ範囲外の市町村は収集されず、住所不明の物件は残る。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [
        {"id": "in-1", "title": "範囲内の家", "url": "u1", "price": "150万円",
         "address": "鹿児島県薩摩川内市", "layout": "4DK"},
        {"id": "out-1", "title": "離島の家", "url": "u2", "price": "100万円",
         "address": "鹿児島県奄美市", "layout": "4DK"},
        {"id": "na-1", "title": "住所不明の家", "url": "u3", "price": "120万円",
         "layout": "4DK"},
    ]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"target_areas": ["薩摩川内市", "鹿屋市"]},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))
    out = capsys.readouterr().out
    assert "リサーチ範囲外のためスキップ: 1件" in out
    html = report.read_text(encoding="utf-8")
    assert "範囲内の家" in html
    assert "離島の家" not in html
    assert "住所不明の家" in html   # 住所が読めない物件は落とさない


def test_price_ceiling_and_unknown_price_filter(tmp_path, capsys):
    """高額物件と「応相談」は収集段階で外れる(2026-07 ユーザー判断)。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [
        {"id": "ok", "title": "買える物件", "url": "u1", "price": "150万円",
         "layout": "4DK", "description": "残置物あり"},
        {"id": "exp", "title": "高すぎる物件", "url": "u2", "price": "700万円",
         "layout": "5LDK"},
        {"id": "unk", "title": "応相談の物件", "url": "u3", "price": "応相談",
         "layout": "4DK"},
    ]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"max_price_yen": 5_000_000, "include_price_unknown": False},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))
    out = capsys.readouterr().out
    assert "価格上限(5,000,000円)超のためスキップ: 1件" in out
    assert "価格応相談のためスキップ: 1件" in out
    html = report.read_text(encoding="utf-8")
    assert "買える物件" in html
    assert "高すぎる物件" not in html
    assert "応相談の物件" not in html


def test_mail_unknown_price_survives_unknown_filter(tmp_path):
    """メール由来の価格不明は「応相談カット」の対象外(読み取り失敗の可能性)。"""
    from unittest.mock import patch
    from email.message import EmailMessage
    from akiya_watcher.main import collect
    from akiya_watcher.scrapers.mailbox import GmailImapScraper

    msg = EmailMessage()
    msg["Subject"] = "新着"
    msg.set_content("鹿児島県薩摩川内市の中古戸建て\n"
                    "https://www.athome.co.jp/kodate/777/\n詳細はリンク先で")

    def fake_fetch(self):
        from akiya_watcher.scrapers.mailbox import extract_listings_from_email
        return extract_listings_from_email(msg)

    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"max_price_yen": 3_000_000, "include_price_unknown": False},
        "sources": [{"id": "g", "type": "gmail_imap", "username": "t@gmail.com"}],
    }
    with patch.object(GmailImapScraper, "fetch_listings", fake_fetch):
        items, *_ = collect(config)
    assert len(items) == 1                      # 捨てられずに台帳へ
    assert items[0][0].listing.price_yen is None


def test_filtered_listing_is_not_marked_delisted(tmp_path, capsys):
    """足切りで除外した物件を「掲載終了(売れた)」と誤記録しない。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [{"id": "x", "title": "値上げされた物件", "url": "u1",
             "price": "300万円", "layout": "4DK"}]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"max_price_yen": 5_000_000},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))          # 1回目: 300万で収録
    capsys.readouterr()

    rows[0]["price"] = "700万円"                     # 値上げで足切り対象に
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    run(str(cfg), report_path=str(report))
    out = capsys.readouterr().out
    assert "掲載終了" not in out                     # 売れた扱いにしない
    assert "最近消えた物件" not in report.read_text(encoding="utf-8")


def test_low_score_new_listing_stays_silent(tmp_path, capsys):
    """低スコア新着は通知されないが台帳レポートには載る(二層構造の回帰テスト)。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [{"id": "quiet-1", "title": "情報の少ない家", "url": "https://example.com/q",
             "price": "600万円", "layout": "3K"}]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))
    out = capsys.readouterr().out
    assert "🆕 新着物件" not in out          # 通知は鳴らない
    assert "[silent]" in out                 # 抑制ログには残る
    assert "情報の少ない家" in report.read_text(encoding="utf-8")  # 台帳には載る


def test_always_notify_source_sends_low_score_new_listing(tmp_path, capsys):
    """注力市に明示したソースは、新着を点数で止めない。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [{"id": "ichiki-1", "title": "情報の少ない家", "url": "https://example.com/ichiki",
             "price": "250万円", "layout": "3K"}]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "notify": {"bundle": True, "heartbeat": False},
        "criteria": {"max_price_yen": 3_000_000},
        "sources": [{"id": "ichiki", "type": "demo", "path": str(demo),
                     "always_notify": True}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg))
    assert "監視 1件 / 通知 1件 / 抑制 0件" in capsys.readouterr().out


def test_mainland_and_island_area_filtering(tmp_path, capsys):
    """鹿児島県本土(枕崎・指宿・南さつま・南九州)は収集され、離島(奄美・西之表等)は除外される。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [
        {"id": "mainland-1", "title": "枕崎の家", "url": "https://example.com/m",
         "price": "200万円", "address": "鹿児島県枕崎市汐見町"},
        {"id": "mainland-2", "title": "指宿の家", "url": "https://example.com/i",
         "price": "250万円", "address": "鹿児島県指宿市十二町"},
        {"id": "island-1", "title": "奄美の家", "url": "https://example.com/a",
         "price": "150万円", "address": "鹿児島県奄美市名瀬"},
        {"id": "island-2", "title": "種子島の家", "url": "https://example.com/t",
         "price": "180万円", "address": "鹿児島県西之表市西之表"},
    ]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {
            "target_areas": ["枕崎市", "指宿市", "南さつま市", "南九州市"],
            "max_price_yen": 3_000_000,
        },
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))
    content = report.read_text(encoding="utf-8")
    assert "枕崎の家" in content
    assert "指宿の家" in content
    assert "奄美の家" not in content
    assert "種子島の家" not in content

