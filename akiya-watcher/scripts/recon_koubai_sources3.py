"""公売・競売ソースの偵察 第3弾 (2026-08-09)。

第2弾の積み残しを潰す:
  1. 国税庁公売: 検索結果の物件行の生HTML (リンク形式・価格・所在地の実体)
  2. KSI: /search/real-estate/ の表示順(入札終了が先頭?)と2ページ目の扱い、
     robots.txt がクエリ付きURLをどう判定するか
  3. BIT: ブラウザと同じ画面遷移 (トップ→エリア選択POST) の再現を試みる
  4. 鹿児島県: 文字コードを直して (apparent_encoding) リンク一覧を取る

DB・通知は使わない読み取り専用。
"""
from __future__ import annotations

import re
import sys
import time
import urllib.robotparser

import requests
from bs4 import BeautifulSoup

UA = "akiya-watcher/0.1 (personal use; recon)"
TIMEOUT = 30
PAUSE_SEC = 3.0


def section(title: str) -> None:
    print(f"\n===== {title} =====")


def recon_nta(session: requests.Session) -> None:
    section("国税庁公売 物件行の生HTML")
    url = ("https://www.koubai.nta.go.jp/auctionx/public/hp0241.php"
           "?addr_id=0&addr_area=0&addr_wide=0&addr_or_line=0&addr_name=0"
           "&zaisan_bunrui_chk%5B100%5D=1&zaisan_bunrui_chk%5B110%5D=1"
           "&zaisan_bunrui_chk%5B120%5D=1&zaisan_bunrui_chk%5B130%5D=1"
           "&zaisan_bunrui_chk%5B190%5D=1&zaisan_bunrui_chk%5B999%5D=1")
    res = session.get(url, timeout=TIMEOUT)
    html = res.text
    print(f"  HTTP {res.status_code} / {len(html):,}文字")
    # 全hrefの形式を集計 (物件詳細への導線の形を知る)
    hrefs = re.findall(r'href="([^"]+)"', html)
    prefixes: dict[str, int] = {}
    for h in hrefs:
        key = h.split("?")[0]
        prefixes[key] = prefixes.get(key, 0) + 1
    print("  href集計 (上位15):")
    for k, v in sorted(prefixes.items(), key=lambda x: -x[1])[:15]:
        print(f"    {v:3d}件 {k}")
    # 「見積価額」の出現と周辺の生HTML
    count = html.count("見積価額")
    print(f"  「見積価額」出現: {count}回")
    idx = html.find("見積価額", html.find("見積価額") + 1)  # 2回目(1回目は検索フォーム)
    if idx > 0:
        print(f"  2回目の周辺生HTML:\n    {html[idx-600:idx+400]!r}")
    # 「売却区分番号」or「物件番号」の周辺
    for kw in ("売却区分番号", "物件番号", "公売財産"):
        i = html.find(kw)
        print(f"  「{kw}」出現位置: {i}")
        if i > 0:
            print(f"    周辺: {html[i-200:i+300]!r}")
            break


def recon_ksi(session: requests.Session) -> None:
    section("KSI 表示順とrobots判定")
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url("https://kankocho.jp/robots.txt")
    rp.read()
    for u in ["https://kankocho.jp/search/real-estate/",
              "https://kankocho.jp/search/real-estate/?page=2",
              "https://kankocho.jp/items/69232/"]:
        print(f"  robots判定 {u}: {rp.can_fetch(UA, u)}")
    res = session.get("https://kankocho.jp/search/real-estate/", timeout=TIMEOUT)
    html = res.text
    soup = BeautifulSoup(html, "html.parser")
    # 状態ラベルの分布 (入札終了ばかりだと1ページ目の価値が低い)
    for label in ("入札終了", "入札中", "受付中", "入札予定", "受付終了", "公開中"):
        print(f"  「{label}」出現: {html.count(label)}回")
    # ページャの有無
    pager_links = [a["href"] for a in soup.find_all("a", href=True)
                   if "page" in a["href"]]
    print(f"  ページャらしきリンク: {pager_links[:8]}")
    # 都道府県の絞り込みリンク (robotsで許可された形があるか)
    pref_links = [a["href"] for a in soup.find_all("a", href=True)
                  if "鹿児島" in a.get_text() or "kagoshima" in a["href"].lower()]
    print(f"  鹿児島関連リンク: {pref_links[:5]}")
    # 鹿児島物件のカード全文 (1件)
    for a in soup.find_all("a", href=True):
        if re.match(r"^/items/\d+/?$", a["href"]) and "鹿児島" in str(a):
            card = a
            for _ in range(3):
                if card.parent:
                    card = card.parent
            print("  鹿児島物件カード全文:")
            print("    " + card.get_text(" | ", strip=True)[:500])
            break


def recon_bit(session: requests.Session) -> None:
    section("BIT ブラウザ遷移の再現")
    top = session.get("https://www.bit.courts.go.jp/app/top/pt001/h01",
                      timeout=TIMEOUT)
    html = top.text
    # blockCls / tabId / prefecturesId がJS内でどう使われているか
    for kw in ("blockCls", "prefecturesId", "courtId"):
        ms = list(re.finditer(kw + r"""[^;{}]{0,120}""", html))
        print(f"  「{kw}」出現 {len(ms)}回 (先頭3):")
        for m in ms[:3]:
            print(f"    {m.group(0)[:140]!r}")
    # 鹿児島の値の対応付け (selectのoptionか、JS配列か)
    for m in list(re.finditer(r".{200}鹿児島.{80}", html))[:3]:
        print(f"  「鹿児島」周辺: {m.group(0)[-260:]!r}")
    # トップのform一覧と hidden 値
    soup = BeautifulSoup(html, "html.parser")
    for form in soup.find_all("form")[:4]:
        print(f"  form action={form.get('action')} method={form.get('method')}")
        for inp in form.find_all("input")[:10]:
            print(f"    input name={inp.get('name')} value={inp.get('value')!r}")
    # エリア選択POSTの試行 (ブロック=九州・沖縄 を想定した値をいくつか)
    for block in ("08", "9", "kyushu"):
        res = session.post("https://www.bit.courts.go.jp/app/area/pk001/h01",
                           data={"tabId": "01", "blockCls": block},
                           timeout=TIMEOUT)
        title = ""
        m = re.search(r"<title>([^<]+)</title>", res.text)
        if m:
            title = m.group(1)
        kag = res.text.count("鹿児島")
        print(f"  POST pk001 blockCls={block}: HTTP {res.status_code} "
              f"title={title!r} 鹿児島出現={kag}回 ({len(res.text):,}文字)")
        if res.status_code == 200 and kag > 0:
            for mm in list(re.finditer(r".{150}鹿児島.{150}", res.text))[:2]:
                print(f"    周辺: {mm.group(0)!r}")
            break
        time.sleep(1.0)


def recon_pref(session: requests.Session) -> None:
    section("鹿児島県 公売情報 (文字コード修正版)")
    for url in [
        "https://www.pref.kagoshima.jp/kurashi-kankyo/zei/koubai/index.html",
        "https://www.pref.kagoshima.jp/kensei/nyusatu/zaisan/index.html",
    ]:
        res = session.get(url, timeout=TIMEOUT)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "(なし)"
        print(f"  {url}")
        print(f"    HTTP {res.status_code} / <title>: {title}")
        links = [(a.get_text(" ", strip=True)[:60], a["href"])
                 for a in soup.find_all("a", href=True)
                 if any(k in a.get_text() for k in
                        ("公売", "売却", "オークション", "物件", "入札"))]
        print(f"    関連リンク {len(links)}件 (先頭10件):")
        for text, href in links[:10]:
            print(f"      [{text}] {href}")
        time.sleep(PAUSE_SEC)


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = UA
    recon_nta(session)
    time.sleep(PAUSE_SEC)
    recon_ksi(session)
    time.sleep(PAUSE_SEC)
    recon_bit(session)
    time.sleep(PAUSE_SEC)
    recon_pref(session)
    print("\n===== 偵察第3弾 完了 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
