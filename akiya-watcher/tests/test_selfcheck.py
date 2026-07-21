"""セルフ診断(--check)と設定エラーの日本語メッセージのテスト。"""
import pytest
import yaml

from akiya_watcher.main import ConfigError, load_config, self_check
from akiya_watcher.scrapers.mailbox import _price_in


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError, match="見つかりません"):
        load_config(str(tmp_path / "nai.yaml"))


def test_broken_yaml_gives_japanese_error(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("sources:\n  - id: a\n   type: b\n", encoding="utf-8")  # インデント不正
    with pytest.raises(ConfigError, match="書き方に間違い"):
        load_config(str(p))


def _write(tmp_path, config):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    return str(p)


def test_check_passes_with_demo_config(tmp_path, capsys):
    demo = tmp_path / "demo.json"
    demo.write_text("[]", encoding="utf-8")
    path = _write(tmp_path, {
        "criteria": {"target_areas": ["薩摩川内市"]},
        "sources": [{"id": "demo", "type": "demo", "path": str(demo)}],
    })
    assert self_check(path) == 0
    out = capsys.readouterr().out
    assert "すべてOK" in out


def test_check_detects_placeholder_gmail(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    path = _write(tmp_path, {
        "sources": [{"id": "gmail_portal_mail", "type": "gmail_imap",
                     "username": "your-address@gmail.com"}],
    })
    assert self_check(path) == 1
    out = capsys.readouterr().out
    assert "Gmailアドレスが未設定です" in out


def test_check_username_from_env(tmp_path, capsys, monkeypatch):
    """アドレスは環境変数 GMAIL_USERNAME からも読める(公開リポジトリ対策)。"""
    monkeypatch.setenv("GMAIL_USERNAME", "harumi@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "xxxx")
    path = _write(tmp_path, {
        "sources": [{"id": "g", "type": "gmail_imap",
                     "username_env": "GMAIL_USERNAME"}],
        "notify": {"email": {"username_env": "GMAIL_USERNAME"}},
    })
    assert self_check(path) == 0
    out = capsys.readouterr().out
    assert "harumi@gmail.com" in out
    assert "通知メールの宛先: harumi@gmail.com" in out


def test_check_detects_missing_password(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    path = _write(tmp_path, {
        "sources": [{"id": "g", "type": "gmail_imap",
                     "username": "harumi@gmail.com"}],
    })
    assert self_check(path) == 1
    out = capsys.readouterr().out
    assert "アプリパスワードが未設定" in out


# ---------------------------------------------------------------- メール価格の向き

def test_mail_arrow_price_reads_new_price():
    """「300万円→100万円」は右側(100万)が現在価格。左は変更前価格。"""
    price, prev = _price_in("値下げしました 300万円→100万円 鹿児島県霧島市")
    assert price == 1_000_000
    assert prev == 3_000_000


def test_mail_single_price():
    price, prev = _price_in("価格: 180万円")
    assert price == 1_800_000
    assert prev is None