"""メール1タップ⭐キープ登録のテスト。

流れ: 通知メールの「⭐キープ」リンク → 件名keepの自分宛メール →
keep_mail.py が読む → 台帳(keeps) → 追跡リスト(watch)へ合流 →
まとめメールで受付報告。この一連を部品ごとに検証する。
"""
from email.message import EmailMessage

from akiya_watcher.keep_mail import parse_keep_mail, subject_is_keep
from akiya_watcher.main import build_patrol_summary, merge_keep_entries
from akiya_watcher.notify import format_message, keep_mailto_line, text_to_html
from akiya_watcher.storage import Store


def keep_mail(subject: str, body: str, date: str = "Sat, 01 Aug 2026 10:00:00 +0900",
              ) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "watashi@example.com"
    msg["To"] = "watashi@example.com"
    msg["Date"] = date
    msg.set_content(body)
    return msg


# ------------------------------------------------------------ 件名の判定

def test_subject_keep_variants():
    assert subject_is_keep("keep")
    assert subject_is_keep("Keep")
    assert subject_is_keep("KEEP ")
    assert subject_is_keep("Re: keep")          # 返信でも受け付ける
    assert subject_is_keep("Fwd: keep")
    assert subject_is_keep("ｋｅｅｐ")           # 全角もNFKCで許容
    assert subject_is_keep("keep 伊佐の家")      # 件名にメモを足しても良い


def test_subject_not_keep():
    assert not subject_is_keep("🏠 巡回まとめ: 値下げ1件")
    assert not subject_is_keep("お問い合わせ keep について")  # 先頭以外は不可
    assert not subject_is_keep("")
    assert not subject_is_keep(None)


# ------------------------------------------------------------ 本文の解釈

def test_parse_keep_mail_basic():
    msg = keep_mail("keep", "https://akiya.example.jp/bukken/123\n")
    entries = parse_keep_mail(msg)
    assert len(entries) == 1
    assert entries[0]["url"] == "https://akiya.example.jp/bukken/123"
    assert entries[0]["note"] == ""
    assert entries[0]["added_on"] == "2026-08-01"


def test_parse_keep_mail_with_note():
    msg = keep_mail("keep", "https://akiya.example.jp/bukken/123\n蔵あり。来週電話する")
    entries = parse_keep_mail(msg)
    assert entries[0]["note"] == "蔵あり。来週電話する"


def test_parse_keep_mail_wrong_subject_or_empty():
    assert parse_keep_mail(keep_mail("巡回まとめ", "https://a.jp/1")) == []
    assert parse_keep_mail(keep_mail("keep", "URLを貼り忘れた")) == []


def test_parse_keep_mail_ignores_map_links():
    body = ("https://akiya.example.jp/bukken/9\n"
            "https://maps.google.com/?q=%E9%9C%A7%E5%B3%B6%E5%B8%82")
    entries = parse_keep_mail(keep_mail("keep", body))
    assert [e["url"] for e in entries] == ["https://akiya.example.jp/bukken/9"]


def test_parse_keep_mail_rejects_bulk_forward():
    # まとめメールを丸ごと転送するとURLだらけ → 誤登録防止のため無視
    body = "\n".join(f"https://akiya.example.jp/bukken/{i}" for i in range(8))
    assert parse_keep_mail(keep_mail("keep", body)) == []


def test_parse_keep_mail_html_body():
    msg = EmailMessage()
    msg["Subject"] = "keep"
    msg["Date"] = "Sat, 01 Aug 2026 10:00:00 +0900"
    msg.add_alternative(
        '<p><a href="https://akiya.example.jp/bukken/55">物件</a></p>',
        subtype="html")
    entries = parse_keep_mail(msg)
    assert [e["url"] for e in entries] == ["https://akiya.example.jp/bukken/55"]


# ------------------------------------------------------------ 台帳への記録

def test_store_upsert_keep(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.upsert_keep("https://a.jp/1", "", "2026-08-01") is True
    assert store.upsert_keep("https://a.jp/1", "", "2026-08-01") is False  # 再読込
    # メモ後付け: 2通目のkeepメールでメモを足せる
    assert store.upsert_keep("https://a.jp/1", "電話済み", "2026-08-02") is False
    entries = store.keep_entries()
    assert len(entries) == 1
    assert entries[0]["note"] == "電話済み"
    assert entries[0]["added_on"] == "2026-08-01"  # 初回登録日を保持
    store.close()


# ------------------------------------------------- 追跡リストへの合流

def test_merge_keep_entries_into_watch():
    sources = [
        {"id": "kirishima", "type": "generic_html", "enabled": True},
        {"id": "watchlist", "type": "watch", "enabled": True,
         "entries": [{"url": "https://a.jp/config-entry", "note": "手動"}]},
    ]
    keeps = [
        {"url": "https://a.jp/config-entry", "note": "", "added_on": "2026-08-01"},
        {"url": "https://a.jp/new-keep", "note": "蔵あり", "added_on": "2026-08-01"},
    ]
    added = merge_keep_entries(sources, keeps)
    assert added == 1  # config直書き分は重複登録しない
    entries = sources[1]["entries"]
    assert entries[1]["url"] == "https://a.jp/new-keep"
    assert "⭐メールでキープ登録 2026-08-01" in entries[1]["note"]
    assert "蔵あり" in entries[1]["note"]
    # 再実行しても増えない (毎巡回呼ばれるため)
    assert merge_keep_entries(sources, keeps) == 0


def test_merge_keep_entries_without_watch_source():
    assert merge_keep_entries([{"id": "x", "type": "rss"}],
                              [{"url": "https://a.jp/1"}]) == 0


# ------------------------------------------------------------ 通知への配線

def test_keep_mailto_line(monkeypatch):
    monkeypatch.setenv("GMAIL_USERNAME", "watashi@example.com")
    line = keep_mailto_line("https://akiya.example.jp/bukken/123?p=1")
    assert line.startswith("⭐キープ: mailto:watashi@example.com?subject=keep&body=")
    assert "https%3A%2F%2Fakiya.example.jp%2Fbukken%2F123%3Fp%3D1" in line


def test_keep_mailto_line_without_env(monkeypatch):
    monkeypatch.delenv("GMAIL_USERNAME", raising=False)
    assert keep_mailto_line("https://a.jp/1") == ""


def test_text_to_html_renders_keep_button(monkeypatch):
    monkeypatch.setenv("GMAIL_USERNAME", "watashi@example.com")
    html = text_to_html("URL: https://a.jp/1\n" + keep_mailto_line("https://a.jp/1"))
    assert '<a href="mailto:watashi@example.com?subject=keep&amp;body=' in html
    assert "⭐この物件をキープ" in html
    assert "body=https" not in html.split("</a>")[-1]  # 生のmailtoを残さない


def test_format_message_includes_keep_link(monkeypatch):
    from akiya_watcher.models import Listing, ListingContext, Score
    from akiya_watcher.storage import Diff
    monkeypatch.setenv("GMAIL_USERNAME", "watashi@example.com")
    ls = Listing(source="kirishima", listing_id="1", title="古民家",
                 url="https://a.jp/1", price_yen=1000000)
    diff = Diff(kind="new", listing=ls,
                context=ListingContext(is_new=True, current_price_yen=1000000))
    text = format_message(diff, Score(total=10))
    assert "⭐キープ: mailto:" in text
    # 追跡済み (watch) には付けない
    ls_watch = Listing(source="watch", listing_id="2", title="⭐追跡: 家",
                       url="https://a.jp/2", price_yen=None)
    diff_w = Diff(kind="new", listing=ls_watch,
                  context=ListingContext(is_new=True))
    assert "⭐キープ: mailto:" not in format_message(diff_w, Score(total=10))


def test_patrol_summary_announces_keep_added():
    text = build_patrol_summary(
        [], keep_added_texts=["⭐ キープ登録を受け付けました (メール1タップ登録)\n"
                              "URL: https://a.jp/1\n→ 追跡リスト入り。"])
    assert "⭐キープ登録1件" in text.splitlines()[0]  # 件名に出る
    assert "受け付けました" in text
