"""⭐キープ機能(理想条件: 残置物×立地)のテスト。"""
import json

import yaml

from akiya_watcher.criteria import Scorer, is_keep
from akiya_watcher.models import Listing, ListingContext


def make(**kw) -> Listing:
    base = dict(source="t", listing_id="1", title="テスト物件", url="u")
    base.update(kw)
    return Listing(**base)


CRITERIA = {"priority_cities": ["薩摩川内市"]}


def test_is_keep_requires_zanchi_and_location():
    scorer = Scorer(CRITERIA)
    ctx = ListingContext(is_new=False)
    # 残置物 × 利便 → キープ
    assert is_keep(scorer.score(
        make(price_yen=1_500_000, description="残置物あり スーパー近く"), ctx))
    # 残置物 × 注力エリア → キープ
    assert is_keep(scorer.score(
        make(price_yen=1_500_000, address="鹿児島県薩摩川内市",
             description="残置物あり"), ctx))
    # 残置物だけ(立地情報なし) → キープではない
    assert not is_keep(scorer.score(
        make(price_yen=1_500_000, description="残置物あり"), ctx))
    # 立地だけ(残置物なし) → キープではない
    assert not is_keep(scorer.score(
        make(price_yen=1_500_000, address="鹿児島県薩摩川内市",
             description="きれいな家"), ctx))
    # 残置物 × 蔵・旧家 → 立地がなくてもキープ (本丸シグナル)
    assert is_keep(scorer.score(
        make(price_yen=1_500_000, description="残置物あり 土蔵・納屋付きの旧家"), ctx))


def test_wealth_signal_scoring():
    scorer = Scorer(CRITERIA)
    ctx = ListingContext(is_new=False)
    s = scorer.score(make(price_yen=2_000_000,
                          description="母屋と離れ、土蔵付きの屋敷。残置物あり"), ctx)
    assert "🏺蔵・旧家" in s.badges
    assert "土蔵" in s.matched_keywords
    # 「冷蔵庫」には誤反応しない
    s2 = scorer.score(make(price_yen=2_000_000, description="冷蔵庫・洗濯機あり"), ctx)
    assert "🏺蔵・旧家" not in s2.badges


def _config(tmp_path, demo):
    config = {
        "db_path": str(tmp_path / "db.sqlite"),
        "criteria": {"priority_cities": ["薩摩川内市"]},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    }
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return cfg


KEEP_ROW = {"id": "k1", "title": "キープ対象の家", "url": "u1", "price": "150万円",
            "layout": "4DK", "address": "鹿児島県薩摩川内市",
            "description": "残置物あり スーパー徒歩5分"}


def test_keep_section_in_report(tmp_path):
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps([KEEP_ROW], ensure_ascii=False), encoding="utf-8")
    report = tmp_path / "report.html"
    run(str(_config(tmp_path, demo)), report_path=str(report))
    html = report.read_text(encoding="utf-8")
    assert "⭐ キープ" in html
    assert html.index("キープ対象の家") < html.index("全物件ランキング")


def test_keep_change_notifies_even_without_drop(tmp_path, capsys):
    """キープ物件は値下げなしの記載変更でも通知される。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    demo.write_text(json.dumps([KEEP_ROW], ensure_ascii=False), encoding="utf-8")
    cfg = _config(tmp_path, demo)

    run(str(cfg))
    capsys.readouterr()

    changed = dict(KEEP_ROW, description="残置物あり スーパー徒歩5分 商談中となりました")
    demo.write_text(json.dumps([changed], ensure_ascii=False), encoding="utf-8")
    run(str(cfg))
    out = capsys.readouterr().out
    assert "🔄 掲載変更" in out           # キープなので沈黙せず通知される


def test_keep_delisting_notifies(tmp_path, capsys):
    """キープ物件が掲載から消えたら「売れた可能性」として速報される。"""
    from akiya_watcher.main import run
    demo = tmp_path / "demo.json"
    other = {"id": "k2", "title": "残る家", "url": "u2", "price": "100万円",
             "layout": "3K"}
    demo.write_text(json.dumps([KEEP_ROW, other], ensure_ascii=False),
                    encoding="utf-8")
    cfg = _config(tmp_path, demo)

    run(str(cfg))
    capsys.readouterr()

    demo.write_text(json.dumps([other], ensure_ascii=False), encoding="utf-8")
    run(str(cfg))
    out = capsys.readouterr().out
    assert "⭐ キープ物件が掲載終了(売れた可能性)" in out
    assert "キープ対象の家" in out