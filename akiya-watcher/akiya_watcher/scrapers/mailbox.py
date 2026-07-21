"""Gmail(IMAP)メール解析アダプタ。

楽待・アットホーム・SUUMO等の規約でスクレイピングできないポータルを、
規約違反なしにカバーする正攻法:
  1. ユーザーが各ポータルで「条件保存+新着メール通知」を設定する
  2. Gmailのフィルタで通知メールに専用ラベル(例: bukken)を付ける
  3. このアダプタがIMAPでそのラベルを読み、メール本文から物件を抽出する

自分宛てに届いたメールを自分で処理するだけなので規約問題はない。
抽出された物件は空き家バンクと同じ Listing に正規化され、同じ
スコアリング・差分検知・通知に合流する。お気に入り物件の更新通知
メールも読めば、同一URLの価格変化として値下げ検知が自動で効く。

認証: Googleアカウントの2段階認証を有効にして「アプリパスワード」を発行し、
環境変数 GMAIL_APP_PASSWORD に設定する(configやgitには書かない)。

注意: IMAPのフォルダ名に日本語ラベルを使うと文字コード(修正UTF-7)の
問題が出るため、ラベル名は半角英数(例: bukken)を推奨。
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import imaplib
import os
import re
from datetime import date, timedelta
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ..criteria import parse_price_yen
from ..models import Listing
from .base import BaseScraper

# ポータルのドメイン → 情報源名。config の portal_domains で上書き可能。
DEFAULT_PORTAL_DOMAINS = {
    "suumo.jp": "SUUMO",
    "athome.co.jp": "アットホーム",
    "rakumachi.jp": "楽待",
    "kenbiya.com": "健美家",
    "jmty.jp": "ジモティー",
    "homes.co.jp": "LIFULL HOME'S",
    "nifty.com": "ニフティ不動産",
    "ieichiba.com": "家いちば",
}

URL_PAT = re.compile(r"https?://[^\s<>\"']+")
# 価格らしい文字列だけを対象にする(郵便番号や年数の誤検出を防ぐ)
PRICE_PAT = re.compile(r"[0-9,.]+\s*(?:億[0-9,.]*万?|万)\s*円|[0-9]{1,3}(?:,[0-9]{3})+円")
# 値下げ表記「300万円→100万円」: 右側が現在価格
ARROW_PAT = re.compile(
    r"([0-9,.]+\s*(?:億[0-9,.]*万?|万)\s*円)\s*(?:→|⇒)\s*"
    r"([0-9,.]+\s*(?:億[0-9,.]*万?|万)\s*円)")
# 物件ではない定番リンク (実際のアットホームメールで確認した宣伝・案内リンク)
JUNK_TITLE_PAT = re.compile(
    r"コチラ|こちら|掲載会社|査定|見積もり|引越し|ライブラリー|新築マンション"
    r"|すべての|おすすめ.*(?:をみる|情報)|ＰＲ|PR|キャンペーン|配信|停止"
    r"|unsubscribe|ログイン|お問い合わせ|会員|マイページ|アプリ|規約|ヘルプ")
# 住所らしさ (物件行の判定補助)
ADDRESS_HINT_PAT = re.compile(r"[一-龥]{2,4}[都道府県]|[一-龥]{2,8}[市郡町村]")


def _portal_of(url: str, domains: dict[str, str]) -> str | None:
    host = urlparse(url).netloc.lower()
    for domain, name in domains.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def _canonical(url: str) -> str:
    """トラッキング用クエリを除いた物件ID用の正規URL。"""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def _price_in(text: str) -> tuple[int | None, int | None]:
    """(現在価格, 変更前価格) を返す。「300万円→100万円」は右が現在価格。"""
    m = ARROW_PAT.search(text)
    if m:
        return parse_price_yen(m.group(2)), parse_price_yen(m.group(1))
    m = PRICE_PAT.search(text)
    return (parse_price_yen(m.group(0)) if m else None), None


def _walk_bodies(msg: email.message.Message):
    """(content_type, decoded_text) を順に返す。"""
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/html", "text/plain"):
            continue
        try:
            yield ctype, part.get_content()
        except Exception:
            continue


def extract_listings_from_email(msg: email.message.Message,
                                domains: dict[str, str] | None = None,
                                ) -> list[Listing]:
    """1通のメールから物件リンクを抽出して Listing に正規化する。

    ポータルごとのHTML構造には依存せず、「ポータルドメインへのリンク+
    その周辺テキスト(タイトル・価格・説明)」という汎用構造で拾う。
    実際の通知メールが届き始めたら、必要に応じてポータル別の精密パーサを
    ここに足す。
    """
    domains = domains or DEFAULT_PORTAL_DOMAINS
    subject = str(msg.get("Subject", "") or "")
    found: dict[str, Listing] = {}

    for ctype, body in _walk_bodies(msg):
        if ctype == "text/html":
            soup = BeautifulSoup(body, "html.parser")
            for a in soup.find_all("a", href=True):
                portal = _portal_of(a["href"], domains)
                if not portal:
                    continue
                block = a.find_parent(["td", "li", "div", "p"]) or a.parent
                context = block.get_text(" ", strip=True)[:500] if block else ""
                title = a.get_text(" ", strip=True) or subject
                _add(found, portal, a["href"], title, context)
        else:
            lines = body.splitlines()
            for i, line in enumerate(lines):
                for m in URL_PAT.finditer(line):
                    portal = _portal_of(m.group(0), domains)
                    if not portal:
                        continue
                    window = lines[max(0, i - 3): i + 3]
                    context = " ".join(x.strip() for x in window if x.strip())[:500]
                    # タイトル: 直前の行のうち、URLでも価格行でもないものを優先
                    prev_lines = [x.strip() for x in reversed(lines[max(0, i - 3): i])
                                  if x.strip() and not URL_PAT.search(x)]
                    title = next((x for x in prev_lines if not PRICE_PAT.search(x)),
                                 prev_lines[0] if prev_lines else subject)
                    _add(found, portal, m.group(0), title, context)

    return list(found.values())


def _add(found: dict[str, Listing], portal: str, url: str,
         title: str, context: str) -> None:
    # 宣伝・案内リンクは物件ではないので拾わない
    if JUNK_TITLE_PAT.search(title or ""):
        return
    price, prev_price = _price_in(context)
    # 価格も住所らしき文字列も無いリンクは物件行とみなさない (誤検出防止)
    if price is None and not ADDRESS_HINT_PAT.search(context):
        return
    canon = _canonical(url)
    listing_id = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
    prev = found.get(canon)
    # 同じ物件が複数箇所でリンクされる場合、価格が取れている方を優先
    if prev is not None and (prev.price_yen is not None or price is None):
        return
    found[canon] = Listing(
        source=f"mail:{portal}",
        listing_id=listing_id,
        title=(title or "(無題)")[:120],
        url=url,
        price_yen=price,
        description=context,
        advertised_previous_price_yen=prev_price,
        raw={"canonical_url": canon},
    )


class GmailImapScraper(BaseScraper):
    source_id = "gmail_imap"
    full_snapshot = False  # メールに載らない=掲載終了ではない

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", "gmail_imap")
        self.host = config.get("imap_host", "imap.gmail.com")
        # アドレスは config 直書きか、環境変数 GMAIL_USERNAME (公開リポジトリでは
        # 環境変数推奨 — メールアドレスをコードに残さない)
        self.username = config.get("username") or os.environ.get(
            config.get("username_env", "GMAIL_USERNAME"), "")
        self.password_env = config.get("password_env", "GMAIL_APP_PASSWORD")
        self.folder = config.get("folder", "bukken")
        self.lookback_days = config.get("lookback_days", 3)
        domains = config.get("portal_domains")
        self.domains = ({d: d for d in domains} if isinstance(domains, list)
                        else domains or DEFAULT_PORTAL_DOMAINS)

    def fetch_listings(self) -> list[Listing]:
        if not self.username:
            raise RuntimeError(
                "Gmailアドレスが未設定 (環境変数 GMAIL_USERNAME を設定)")
        password = os.environ.get(self.password_env)
        if not password:
            raise RuntimeError(
                f"環境変数 {self.password_env} が未設定 (Gmailアプリパスワード)")

        since = (date.today() - timedelta(days=self.lookback_days))
        conn = imaplib.IMAP4_SSL(self.host)
        try:
            conn.login(self.username, password)
            typ, _ = conn.select(f'"{self.folder}"', readonly=True)
            if typ != "OK":
                raise RuntimeError(f"IMAPフォルダ '{self.folder}' を開けない"
                                   " (Gmailのラベル名。半角英数を推奨)")
            typ, data = conn.search(None, f'(SINCE {since.strftime("%d-%b-%Y")})')
            listings: list[Listing] = []
            for num in (data[0].split() if typ == "OK" and data and data[0] else []):
                typ, msg_data = conn.fetch(num, "(BODY.PEEK[])")
                if typ != "OK" or not msg_data or msg_data[0] is None:
                    continue
                msg = email.message_from_bytes(
                    msg_data[0][1], policy=email.policy.default)
                listings.extend(extract_listings_from_email(msg, self.domains))
            return listings
        finally:
            try:
                conn.logout()
            except Exception:
                pass
