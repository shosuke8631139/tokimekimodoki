"""レポートのメール添付機能のテスト (SMTP送信はせず、メール組み立てのみ検証)。"""
from akiya_watcher.notify import Notifier


def test_build_mail_with_attachment(tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<h1>テストレポート</h1>", encoding="utf-8")
    n = Notifier(email={"username": "test@gmail.com"})
    msg = n._build_mail("本文です", subject="📋 物件台帳レポート",
                        attachment=str(report))
    assert msg["Subject"] == "📋 物件台帳レポート"
    assert msg["To"] == "test@gmail.com"
    atts = [p for p in msg.iter_attachments()]
    assert len(atts) == 1
    assert atts[0].get_filename() == "report.html"
    assert "テストレポート" in atts[0].get_content()


def test_build_mail_missing_attachment_is_skipped(tmp_path):
    n = Notifier(email={"username": "test@gmail.com"})
    msg = n._build_mail("本文", attachment=str(tmp_path / "nai.html"))
    assert list(msg.iter_attachments()) == []


def test_subject_defaults_to_first_line():
    n = Notifier(email={"username": "test@gmail.com"})
    msg = n._build_mail("🔻 値下げ検知 (▼67%)\n物件名: テスト")
    assert msg["Subject"] == "🔻 値下げ検知 (▼67%)"


def test_send_report_without_email_config_is_noop(tmp_path):
    n = Notifier()  # 通知先なし
    n.send_report(str(tmp_path / "r.html"))  # 例外にならないこと


def test_mail_has_html_alternative_with_clickable_links():
    """メールにはHTML版が併送され、URLがタップできるリンクになる。"""
    n = Notifier(email={"username": "test@gmail.com"})
    msg = n._build_mail("物件です\nhttps://example.com/bukken/1?a=1&b=2")
    html_part = msg.get_body(preferencelist=("html",))
    assert html_part is not None
    content = html_part.get_content()
    assert '<a href="https://example.com/bukken/1?a=1&amp;b=2">' in content
    assert "<br>" in content