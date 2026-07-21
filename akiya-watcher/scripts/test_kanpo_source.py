"""接続テスト第5弾: 官報(インターネット版)の構造偵察。

狙い: 家庭裁判所の「相続財産清算人選任」公告を自動巡回に組み込むための下調べ。
確認すること:
  1. 官報サイトのrobots.txtが自動取得を許しているか
  2. 日々の官報のページ構成 (目次HTML? PDF? URLの規則)
  3. 裁判所公告(相続財産清算人)がどこに載り、テキストとして抜けるか
"""
import datetime
import re
import sys
import time

import requests

UA = {"User-Agent": "akiya-watcher/0.1 (personal use)"}
WAIT = 2.0


def fetch(url: str, timeout: int = 20) -> requests.Response | None:
    time.sleep(WAIT)
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        print(f"  GET {url} -> {r.status_code} "
              f"({r.headers.get('Content-Type', '?')}, {len(r.content):,} bytes)")
        return r
    except Exception as e:
        print(f"  GET {url} -> 失敗 {type(e).__name__}: {e}")
        return None


def show_links(html: str, base_url: str, limit: int = 40, contains: str = "") -> list[str]:
    """aタグの href とテキストを一覧表示し、hrefのリストを返す。"""
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())[:60]
        href = urljoin(base_url, a["href"])
        if contains and (contains not in text and contains not in href):
            continue
        out.append(href)
        if len(out) <= limit:
            print(f"    [{text}] {href}")
    if len(out) > limit:
        print(f"    ... 他{len(out) - limit}件")
    return out


def show_keyword_context(text: str, keyword: str, width: int = 120, limit: int = 5):
    for i, m in enumerate(re.finditer(re.escape(keyword), text)):
        if i >= limit:
            break
        s = max(0, m.start() - width // 2)
        snippet = " ".join(text[s:s + width].split())
        print(f"    …{snippet}…")


BASES = [
    "https://www.kanpo.go.jp",      # 新・官報発行サイト(2025年の電子化以降の可能性)
    "https://kanpou.npb.go.jp",     # 国立印刷局 インターネット版官報(従来)
]

print("===== 1. robots.txt とトップページ =====")
tops: dict[str, str] = {}
for base in BASES:
    print(f"--- {base} ---")
    r = fetch(f"{base}/robots.txt")
    if r is not None and r.status_code == 200:
        print("  robots.txt 冒頭:")
        for line in r.text.splitlines()[:20]:
            print(f"    {line}")
    r = fetch(f"{base}/")
    if r is not None and r.status_code == 200:
        tops[base] = r.text
        m = re.search(r"<title>(.*?)</title>", r.text, re.S)
        print(f"  タイトル: {m.group(1).strip() if m else '?'}")

print("\n===== 2. トップページのリンク構造 =====")
for base, html in tops.items():
    print(f"--- {base} のリンク(先頭40件) ---")
    show_links(html, base + "/", limit=40)

print("\n===== 3. 「裁判所」「公告」「相続」を含むリンク・記述 =====")
court_links: list[str] = []
for base, html in tops.items():
    print(f"--- {base} ---")
    for kw in ("裁判所", "公告", "相続", "号外", "本紙", "目次"):
        links = show_links(html, base + "/", limit=6, contains=kw)
        court_links.extend(links[:3])
    text = re.sub(r"<[^>]+>", " ", html)
    for kw in ("裁判所", "相続"):
        print(f"  本文中の「{kw}」周辺:")
        show_keyword_context(text, kw)

print("\n===== 4. 日付URLの規則を試す(従来型: /YYYYMMDD/) =====")
today = datetime.date.today()
for d in (today, today - datetime.timedelta(days=1), today - datetime.timedelta(days=3)):
    ymd = d.strftime("%Y%m%d")
    for base in BASES:
        r = fetch(f"{base}/{ymd}/")
        if r is not None and r.status_code == 200:
            print(f"  ✅ {base}/{ymd}/ が存在。リンク:")
            show_links(r.text, f"{base}/{ymd}/", limit=30)
            break

print("\n===== 5. 裁判所公告らしきページを1つ開いてみる =====")
seen = set()
for url in court_links:
    if url in seen or url.rstrip("/") in [b for b in BASES]:
        continue
    seen.add(url)
    if len(seen) > 4:
        break
    r = fetch(url)
    if r is None or r.status_code != 200:
        continue
    ctype = r.headers.get("Content-Type", "")
    if "pdf" in ctype or url.endswith(".pdf"):
        print("  PDFを検出。テキスト抽出を試す:")
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(r.content))
            text = "".join((p.extract_text() or "") for p in reader.pages[:3])
            print(f"    ページ数: {len(reader.pages)}, 抽出文字数(先頭3頁): {len(text)}")
            print(f"    冒頭: {' '.join(text[:300].split())}")
            for kw in ("相続財産清算人", "相続人", "鹿児島"):
                print(f"    「{kw}」出現: {text.count(kw)}回")
        except Exception as e:
            print(f"    抽出失敗: {type(e).__name__}: {e}")
    elif "html" in ctype:
        text = re.sub(r"<[^>]+>", " ", r.text)
        for kw in ("相続財産清算人", "相続", "裁判所"):
            n = text.count(kw)
            print(f"  「{kw}」出現: {n}回")
            if n:
                show_keyword_context(text, kw, limit=3)
        print("  このページのリンク(公告・裁判所を含むもの):")
        show_links(r.text, url, limit=10, contains="公告")
        show_links(r.text, url, limit=10, contains="裁判所")

print("\n===== テスト終了 =====")
