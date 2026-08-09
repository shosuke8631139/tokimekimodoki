"""公売・競売ソースの偵察スクリプト (2026-08-09 公売ルート開拓の第一歩)。

目的: 「競売はうまみがない」という噂を、噂ではなく数字で確かめるため、
まず候補サイトの robots.txt と HTML 構造を本番経路 (GitHub Actions) で
確認する。ここで見えた構造に合わせてアダプタを実装する。

候補 (2026-08-09 戦略セッションで選定):
  1. 国税庁 公売情報      — 税金滞納の差押不動産。全国横断+地域絞り込み
  2. KSI官公庁オークション — 自治体の公売・公有財産売却の集約サイト
  3. BIT 裁判所競売       — 鹿児島地裁管内の競売物件 (入札ゼロ→特別売却が狙い目)
  4. 鹿児島県 公売情報     — 県税の差押品 (不動産+動産)

DB・通知は一切使わない読み取り専用。出力はログで人間 (とAI) が読む。
"""
from __future__ import annotations

import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "akiya-watcher/0.1 (personal use; recon)"
TIMEOUT = 30
PAUSE_SEC = 3.0  # サイトをまたぐので同一ホスト連打はないが、礼儀として空ける

TARGETS = [
    ("国税庁 公売情報 トップ",
     "https://www.koubai.nta.go.jp/"),
    ("国税庁 公売情報 不動産検索",
     "https://www.koubai.nta.go.jp/auctionx/public/hp0241.php"),
    ("KSI官公庁オークション トップ",
     "https://kankocho.jp/"),
    ("KSI官公庁オークション 検索",
     "https://kankocho.jp/search/"),
    ("BIT 裁判所競売 トップ",
     "https://www.bit.courts.go.jp/"),
    ("鹿児島県 公売情報 (大隅)",
     "https://www.pref.kagoshima.jp/ab07/kurashi-kankyo/zei/koubai/02koubai-oosumi.html"),
]


def show_robots(session: requests.Session, url: str, seen: set[str]) -> None:
    host = urlparse(url).netloc
    if host in seen:
        return
    seen.add(host)
    robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
    try:
        res = session.get(robots_url, timeout=TIMEOUT)
        if res.status_code == 200:
            body = res.text.strip()
            print(f"  robots.txt ({robots_url}): {res.status_code}")
            for line in body.splitlines()[:30]:
                print(f"    | {line}")
            if len(body.splitlines()) > 30:
                print("    | ... (以下略)")
        else:
            print(f"  robots.txt: {res.status_code} (存在しない = 制限なし)")
    except Exception as e:
        print(f"  robots.txt: 取得失敗 ({e})")


def describe_forms(soup: BeautifulSoup) -> None:
    forms = soup.find_all("form")
    print(f"  フォーム: {len(forms)}個")
    for i, form in enumerate(forms[:4]):
        action = form.get("action", "(なし)")
        method = form.get("method", "GET").upper()
        print(f"    form[{i}] action={action} method={method}")
        for inp in form.find_all(["input", "select"])[:20]:
            name = inp.get("name")
            if not name:
                continue
            if inp.name == "select":
                opts = [(o.get("value", ""), o.get_text(strip=True))
                        for o in inp.find_all("option")[:8]]
                print(f"      select name={name} options={opts}")
            else:
                t = inp.get("type", "text")
                v = inp.get("value", "")
                print(f"      input name={name} type={t} value={v!r}")


def describe_tables(soup: BeautifulSoup) -> None:
    tables = soup.find_all("table")
    print(f"  テーブル: {len(tables)}個")
    for i, table in enumerate(tables[:3]):
        rows = table.find_all("tr")
        print(f"    table[{i}] {len(rows)}行 (先頭3行):")
        for tr in rows[:3]:
            cells = [c.get_text(" ", strip=True)[:40]
                     for c in tr.find_all(["th", "td"])]
            print(f"      {cells}")


def describe_links(soup: BeautifulSoup, base_url: str) -> None:
    keywords = ("公売", "物件", "不動産", "検索", "オークション", "競売", "売却")
    hits = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if any(k in text for k in keywords):
            hits.append((text[:40], urljoin(base_url, a["href"])))
    print(f"  関連リンク: {len(hits)}件 (先頭15件):")
    for text, href in hits[:15]:
        print(f"    [{text}] {href}")


def describe_scripts(soup: BeautifulSoup) -> None:
    """SPA/API の気配を探す (fetch先が分かればHTMLより楽に読める)。"""
    hints = []
    for s in soup.find_all("script"):
        src = s.get("src", "")
        if src:
            if any(k in src.lower() for k in ("app", "main", "chunk", "api")):
                hints.append(f"src={src}")
        else:
            body = (s.string or "")[:4000]
            for k in ("fetch(", "axios", "/api/", "ajax"):
                if k in body:
                    idx = body.find(k)
                    hints.append(f"inline: ...{body[max(0, idx-40):idx+80]!r}...")
                    break
    print(f"  JS手がかり: {len(hints)}件 (先頭8件):")
    for h in hints[:8]:
        print(f"    {h}")


def recon(label: str, url: str, session: requests.Session,
          robots_seen: set[str]) -> None:
    print(f"\n===== {label} =====")
    print(f"  URL: {url}")
    show_robots(session, url, robots_seen)
    try:
        res = session.get(url, timeout=TIMEOUT)
    except Exception as e:
        print(f"  ❌ 取得失敗: {e}")
        return
    ct = res.headers.get("Content-Type", "?")
    print(f"  HTTP {res.status_code} / {ct} / {len(res.text):,}文字 / 最終URL: {res.url}")
    if res.status_code != 200 or "html" not in ct.lower():
        print(f"  本文先頭400字: {res.text[:400]!r}")
        return
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "(なし)"
    print(f"  <title>: {title}")
    describe_forms(soup)
    describe_tables(soup)
    describe_links(soup, str(res.url))
    describe_scripts(soup)


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = UA
    robots_seen: set[str] = set()
    for label, url in TARGETS:
        recon(label, url, session, robots_seen)
        time.sleep(PAUSE_SEC)
    print("\n===== 偵察完了 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
