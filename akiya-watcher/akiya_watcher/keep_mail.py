"""メール1タップの⭐キープ登録 (keepメール読み取り)。

使い方 (ユーザー側):
  通知メールの各物件にある「⭐キープ」リンクをタップすると、
  件名 keep・本文に物件URLが入ったメール下書きが開く。そのまま送信するだけ。
  一言メモを本文に足せば追跡リストの note に残る。

仕組み (機械側):
  巡回のたびにGmailの「すべてのメール」を IMAP で検索し、
  自分宛て・件名が keep で始まるメールから物件URLを取り出して
  台帳DB(keepsテーブル)へ登録→追跡リスト(watch)に自動合流する。

設計の要点:
  - Gmailのフィルタ・ラベル設定は不要。自分宛てメールは「すべてのメール」に
    必ず入るので、\\All フォルダを自動検出して検索する
  - メールが正本: 台帳DB(Actionsキャッシュ)が消えても、keepメールが
    Gmailに残っている限り次の巡回で全件復元される (自己修復)
  - 認証は既存のGmail連携と同じ (GMAIL_USERNAME / GMAIL_APP_PASSWORD)
"""
from __future__ import annotations

import email
import email.policy
import email.utils
import imaplib
import os
import re
import unicodedata
from datetime import date, timedelta

from bs4 import BeautifulSoup

URL_PAT = re.compile(r"https?://[^\s<>\"']+")
# 返信・転送の接頭辞 (「Re: keep」も受け付ける)
_SUBJECT_PREFIX = re.compile(r"^(?:(?:re|fwd?|fw)\s*:\s*)+", re.I)
# 地図リンクは物件URLではない (通知メールを転送した場合の誤登録防止)
_MAP_PAT = re.compile(r"maps\.google\.|google\.[a-z.]+/maps|goo\.gl/maps")
# 1通に貼れるURLの上限。超えたら「まとめメールの丸ごと転送」とみなし無視する
MAX_URLS_PER_MAIL = 5


def subject_is_keep(subject: str, keyword: str = "keep") -> bool:
    """件名が keep (または Re: keep 等) で始まるか。全角・大文字も許容。"""
    s = unicodedata.normalize("NFKC", subject or "").strip()
    s = _SUBJECT_PREFIX.sub("", s).strip()
    return s.lower().startswith(keyword.lower())


def _body_text(msg: email.message.Message) -> str:
    """本文テキスト。text/plain 優先、無ければHTMLから抽出する。"""
    plains, htmls = [], []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            body = part.get_content()
        except Exception:
            continue
        (plains if ctype == "text/plain" else htmls).append(body)
    if plains:
        return "\n".join(plains)
    if htmls:
        soup = BeautifulSoup("\n".join(htmls), "html.parser")
        # URLはリンクの href に入っていて本文テキストに現れないことがある
        hrefs = "\n".join(a["href"] for a in soup.find_all("a", href=True))
        return soup.get_text("\n") + "\n" + hrefs
    return ""


def _mail_date(msg: email.message.Message) -> str:
    try:
        return email.utils.parsedate_to_datetime(
            msg["Date"]).date().isoformat()
    except Exception:
        return date.today().isoformat()


def parse_keep_mail(msg: email.message.Message,
                    subject_keyword: str = "keep") -> list[dict]:
    """keepメール1通から登録エントリを取り出す。

    戻り値: [{"url", "note", "added_on"}]。件名が合わない・URLが無い・
    URLが多すぎる (まとめメールの転送とみられる) 場合は空リスト。
    """
    if not subject_is_keep(str(msg.get("Subject", "") or ""), subject_keyword):
        return []
    text = _body_text(msg)
    urls = []
    for u in URL_PAT.findall(text):
        u = u.rstrip(".,)>\"'")
        if not _MAP_PAT.search(u) and u not in urls:
            urls.append(u)
    if not urls:
        return []
    if len(urls) > MAX_URLS_PER_MAIL:
        print(f"[warn] keepメール: URLが{len(urls)}件と多すぎるため無視します"
              " (まとめメールの転送は登録対象外。物件URLだけ貼ってください)")
        return []
    # メモ = 本文からURLと引用行(>)を除いた残り
    note = URL_PAT.sub(" ", text)
    note = " ".join(line.strip() for line in note.splitlines()
                    if line.strip() and not line.strip().startswith(">"))
    note = re.sub(r"\s+", " ", note).strip()[:300]
    added_on = _mail_date(msg)
    return [{"url": u, "note": note, "added_on": added_on} for u in urls]


def _all_mail_folder(conn: imaplib.IMAP4_SSL) -> str:
    """Gmailの「すべてのメール」フォルダ名を \\All フラグから自動検出する。

    フォルダ名は言語設定で変わる ([Gmail]/All Mail / すべてのメール) ため
    名前決め打ちにしない。見つからなければ INBOX (アーカイブすると
    見えなくなるが動作はする)。
    """
    try:
        typ, data = conn.list()
        for raw in (data or []):
            # 名前は modified UTF-7 のまま扱う (SELECT にもそのまま渡す。
            # 日本語設定のGmailでは「すべてのメール」がエンコードされている)
            line = raw.decode("ascii", errors="replace") \
                if isinstance(raw, bytes) else str(raw)
            if r"\All" not in line:
                continue
            m = re.search(r'"([^"]+)"\s*$', line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "INBOX"


def fetch_keep_entries(cfg: dict) -> list[dict]:
    """IMAPでkeepメールを検索し、登録エントリのリストを返す。"""
    username = cfg.get("username") or os.environ.get(
        cfg.get("username_env", "GMAIL_USERNAME"), "")
    password = os.environ.get(cfg.get("password_env", "GMAIL_APP_PASSWORD"), "")
    if not username or not password:
        raise RuntimeError("GMAIL_USERNAME / GMAIL_APP_PASSWORD が未設定")
    keyword = cfg.get("subject_keyword", "keep")
    lookback = cfg.get("lookback_days", 365)
    since = (date.today() - timedelta(days=lookback)).strftime("%d-%b-%Y")

    conn = imaplib.IMAP4_SSL(cfg.get("imap_host", "imap.gmail.com"))
    try:
        conn.login(username, password)
        folder = cfg.get("folder") or _all_mail_folder(conn)
        typ, _ = conn.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            typ, _ = conn.select("INBOX", readonly=True)
            if typ != "OK":
                raise RuntimeError("IMAPフォルダを開けない")
        # 自分宛て (mailtoの宛先=GMAIL_USERNAME) かつ件名keepだけに絞る
        typ, data = conn.search(
            None, f'(SINCE {since} SUBJECT "{keyword}" TO "{username}")')
        entries: list[dict] = []
        for num in (data[0].split() if typ == "OK" and data and data[0] else []):
            typ, msg_data = conn.fetch(num, "(BODY.PEEK[])")
            if typ != "OK" or not msg_data or msg_data[0] is None:
                continue
            msg = email.message_from_bytes(
                msg_data[0][1], policy=email.policy.default)
            entries.extend(parse_keep_mail(msg, keyword))
        return entries
    finally:
        try:
            conn.logout()
        except Exception:
            pass
