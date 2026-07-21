"""判断支援(実質価格・指値提案)と掲載終了検知のテスト。"""
import json

import yaml

from akiya_watcher.criteria import estimate_disposal_cost_yen, suggest_offer_yen
from akiya_watcher.models import Listing
from akiya_watcher.storage import Store

DAY = 86400


def make(**kw) -> Listing:
    base = dict(source="t", listing_id="1", title="テスト物件", url="u")
    base.update(kw)
    return Listing(**base)


# ---------------------------------------------------------------- 実質価格

def test_disposal_cost_only_for_zanchi_listings():
    assert estimate_disposal_cost_yen(make(description="残置物あり", layout="4DK")) == 340_000
    assert estimate_disposal_cost_yen(make(description="きれいな家", layout="4DK")) is None


def test_disposal_cost_from_floor_area():
    ls = make(description="家財残置", floor_area_sqm=100.0)  # 100㎡ → 5室相当
    assert estimate_disposal_cost_yen(ls) == 400_000


def test_disposal_cost_capped():
    ls = make(description="残置物", layout="9DK")
    assert estimate_disposal_cost_yen(ls) == 500_000


# ---------------------------------------------------------------- 指値提案

def test_suggest_offer_deepens_with_fatigue():
    assert suggest_offer_yen(3_000_000, age_days=200) == 1_800_000        # 6割
    assert suggest_offer_yen(3_000_000, age_days=30, has_drop_history=True) == 1_950_000
    assert suggest_offer_yen(3_000_000, age_days=100) == 2_100_000        # 7割
    assert suggest_offer_yen(3_000_000, age_days=10) is None              # 新鮮な物件には出さない
    assert suggest_offer_yen(None, age_days=200) is None


# ---------------------------------------------------------------- 掲載終了検知

def test_delisting_tracked_and_reported(tmp_path, capsys):
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [
        {"id": "s-1", "title": "残る物件", "url": "u1", "price": "150万円",
         "layout": "4DK", "description": "残置物あり"},
        {"id": "s-2", "title": "売れる物件", "url": "u2", "price": "120万円",
         "layout": "4DK", "description": "現状渡し"},
    ]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    # 1回目: 2件とも掲載中
    run(str(cfg), report_path=str(report))
    capsys.readouterr()

    # 2回目: s-2 が消えた → 掲載終了として記録され、レポートに載る
    demo.write_text(json.dumps(rows[:1], ensure_ascii=False), encoding="utf-8")
    run(str(cfg), report_path=str(report))
    out = capsys.readouterr().out
    assert "掲載終了 1件" in out
    html = report.read_text(encoding="utf-8")
    assert "最近消えた物件" in html
    assert "売れる物件" in html

    # 3回目: 復活したら掲載終了扱いが解除される
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    run(str(cfg), report_path=str(report))
    html = report.read_text(encoding="utf-8")
    assert "最近消えた物件" not in html


def test_report_contains_inquiry_and_map_and_real_price(tmp_path):
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    rows = [{"id": "q-1", "title": "薩摩川内 残置物あり", "url": "u1",
             "price": "150万円", "layout": "4DK",
             "address": "鹿児島県薩摩川内市", "description": "残置物あり現状渡し"}]
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")

    run(str(cfg), report_path=str(report))
    html = report.read_text(encoding="utf-8")
    assert "問い合わせ文" in html
    assert "購入を前提に内見を希望" in html
    assert "google.com/maps" in html
    assert "実質 約" in html          # 150万 + 片付け費34万 = 実質約184万
    assert "184万円" in html