"""取得→判定→差分→通知のエンドツーエンドテスト(デモソース使用)。"""
import json

import yaml

from akiya_watcher.main import run
from akiya_watcher.models import Listing
from akiya_watcher.storage import Store


def _write_config(tmp_path, demo_json_path):
    config = {
        "db_path": str(tmp_path / "listings.db"),
        "criteria": {
            "price_max_yen": 2_000_000,
            "parking_min_slots": 2,
            "floor_area_min_sqm": 80,
            "rooms_min": 4,
            "require_flush_toilet": True,
            "priority_cities": ["鹿児島市"],
        },
        "sources": [
            {"id": "demo", "type": "demo", "path": str(demo_json_path)},
        ],
    }
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return p


def test_pipeline_end_to_end(tmp_path, capsys):
    rows = [
        {
            "id": "e2e-1",
            "title": "合致物件",
            "url": "https://example.com/1",
            "price": "180万円",
            "address": "鹿児島県鹿児島市",
            "floor_area": "98㎡",
            "layout": "5DK",
            "parking": "駐車場:3台",
            "toilet": "水洗(浄化槽)",
            "description": "残置物あり・現状渡し",
        },
        {
            "id": "e2e-2",
            "title": "高すぎる物件",
            "url": "https://example.com/2",
            "price": "500万円",
            "floor_area": "100㎡",
            "parking": "駐車2台",
            "toilet": "水洗",
        },
    ]
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    config_path = _write_config(tmp_path, demo)

    # 初回: 合致1件が「新着」として通知される(webhook未設定→標準出力)
    run(str(config_path))
    out = capsys.readouterr().out
    assert "🆕 新着お宝候補" in out
    assert "合致物件" in out
    assert "高すぎる物件" not in out
    assert "残置物" in out

    # 2回目: 変化なし → 通知されない
    run(str(config_path))
    out = capsys.readouterr().out
    assert "🆕" not in out and "🔄" not in out

    # 価格を下げて3回目 → 「掲載変更」として旧価格つきで通知される
    rows[0]["price"] = "150万円"
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    run(str(config_path))
    out = capsys.readouterr().out
    assert "🔄 掲載変更" in out
    assert "1,800,000円 → 1,500,000円" in out


def test_store_diff_kinds(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    ls = Listing(source="s", listing_id="1", title="t", url="u", price_yen=100)
    d1 = store.upsert(ls)
    assert d1 and d1.kind == "new"
    assert store.upsert(ls) is None
    ls2 = Listing(source="s", listing_id="1", title="t", url="u", price_yen=90)
    d3 = store.upsert(ls2)
    assert d3 and d3.kind == "changed" and d3.old_price_yen == 100
    store.close()
