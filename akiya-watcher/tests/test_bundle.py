"""まとめ送信(1巡回=最大1通)のテスト。2026-08-01 ユーザー要望:
「メールが一気に何件も来て見づらい」対策。
"""
import json
from unittest.mock import patch

import yaml

from akiya_watcher.main import build_patrol_summary, run
from akiya_watcher.models import Listing, ListingContext, Score
from akiya_watcher.notify import Notifier
from akiya_watcher.storage import Diff


def _item(title: str, kind: str = "new", total: int = 10,
          price: int = 1_000_000, prev: int | None = None):
    ls = Listing(source="demo", listing_id=title, title=title,
                 url=f"https://example.com/{title}", price_yen=price)
    ctx = ListingContext(is_new=(kind == "new"), current_price_yen=price,
                         price_changed=prev is not None,
                         previous_price_yen=prev)
    return Diff(kind=kind, listing=ls, context=ctx), Score(total=total)


def test_件名行に件数と最大値下げ率が入る():
    items = [_item("値下げの家", "changed", price=200_000, prev=800_000),   # ▼75%
             _item("小さい値下げ", "changed", price=400_000, prev=500_000),  # ▼20%
             _item("新着の家", "new")]
    text = build_patrol_summary(items)
    subject = text.splitlines()[0]
    assert "巡回まとめ" in subject
    assert "値下げ2件(最大▼75%)" in subject
    assert "新着1件" in subject


def test_値下げが下げ幅順で新着より先に並ぶ():
    items = [_item("新着の家", "new", total=99),
             _item("小さい値下げ", "changed", price=400_000, prev=500_000),
             _item("大きい値下げ", "changed", price=200_000, prev=800_000)]
    text = build_patrol_summary(items)
    assert (text.index("大きい値下げ") < text.index("小さい値下げ")
            < text.index("新着の家"))


def test_キープ掲載終了と定期便も同じ1通に入る():
    items = [_item("新着の家", "new")]
    text = build_patrol_summary(
        items, keep_gone_texts=["⭐ キープ物件が掲載終了(売れた可能性)"],
        heartbeat_text="📮 本日の定期便")
    assert "⭐ キープ物件が掲載終了" in text
    assert "📮 本日の定期便" in text
    # キープは先頭側、定期便は末尾
    assert text.index("⭐") < text.index("新着の家") < text.index("📮")


def _run_config(tmp_path, rows):
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"priority_cities": ["薩摩川内市"]},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return str(cfg)


def _notifiable_rows(n=3):
    return [{
        "id": f"b-{i}",
        "title": f"残置物の家{i}",
        "url": f"https://example.com/{i}",
        "price": "150万円",
        "address": "鹿児島県薩摩川内市",
        "parking": "駐車場:3台",
        "description": "相続のため売却。残置物あり現状渡し。",
    } for i in range(n)]


def test_通知が複数でも送信は1回だけ(tmp_path):
    cfg = _run_config(tmp_path, _notifiable_rows(3))
    sent = []
    with patch.object(Notifier, "send_text",
                      lambda self, text, attachment=None: sent.append(text)):
        run(cfg)
    assert len(sent) == 1                     # 3物件+定期便で1通
    assert "巡回まとめ" in sent[0]
    assert sent[0].count("残置物の家") >= 3
    assert "📮 本日の定期便" in sent[0]        # 定期便も同梱


def test_プレビュー送信は1通だけで見た目確認できる(tmp_path):
    cfg = _run_config(tmp_path, _notifiable_rows(2))
    sent = []
    with patch.object(Notifier, "send_text",
                      lambda self, text, attachment=None: sent.append(text)):
        run(cfg, preview_bundle=True)
    assert len(sent) == 1
    assert "巡回まとめ(プレビュー)" in sent[0]
    assert "📮 本日の定期便" in sent[0]


def test_プレビューは定期便の1日1回メタを消費しない(tmp_path):
    cfg = _run_config(tmp_path, _notifiable_rows(1))
    sent = []
    with patch.object(Notifier, "send_text",
                      lambda self, text, attachment=None: sent.append(text)):
        run(cfg, preview_bundle=True)   # プレビュー
        run(cfg)                        # 直後の通常巡回
    # 通常巡回側でも定期便がちゃんと出る (プレビューがメタを食っていない)
    assert any("📮 本日の定期便" in t and "プレビュー" not in t for t in sent)


def test_同日2回目の巡回では定期便は同梱されない(tmp_path):
    cfg = _run_config(tmp_path, _notifiable_rows(1))
    sent = []
    with patch.object(Notifier, "send_text",
                      lambda self, text, attachment=None: sent.append(text)):
        run(cfg)                               # 1回目: 定期便入り
        rows = _notifiable_rows(1)
        rows[0]["price"] = "100万円"           # 値下げで2回目も通知が出る
        demo = tmp_path / "demo.json"
        demo.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        run(cfg)                               # 2回目
    assert len(sent) == 2
    assert "📮 本日の定期便" in sent[0]
    assert "📮 本日の定期便" not in sent[1]
