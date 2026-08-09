"""公売・競売ソースの偵察 第2弾 (2026-08-09)。

第1弾の結果を受けて、各サイトの「一覧データの実体」まで踏み込む:
  1. 国税庁公売: 検索結果一覧のHTML構造 (物件行・価格・詳細リンクの形)
  2. KSI官公庁オークション: /search/real-estate/ (robots.txtで明示許可) の
     Next.jsペイロードに物件データがどう埋まっているか
  3. BIT裁判所競売: 鹿児島県(prefecturesId=46想定)のPOST検索が通るか
  4. 鹿児島県 公売情報: 現行URL (第1弾の404の修正) の中身

DB・通知は使わない読み取り専用。
"""
from __future__ import annotations

import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

UA = "akiya-watcher/0.1 (personal use; recon)"
TIMEOUT = 30
PAUSE_SEC = 3.0


def section(title: str) -> None:
    print(f"\n===== {title} =====")


def recon_nta(session: requests.Session) -> None:
    """国税庁公売: 全国・全種別の検索結果一覧の構造を見る。"""
    section("国税庁公売 検索結果一覧")
    params = {
        "addr_id": "0", "addr_area": "0", "addr_wide": "0",
        "addr_or_line": "0", "addr_name": "0",
        "zaisan_bunrui_chk[100]": "1", "zaisan_bunrui_chk[110]": "1",
        "zaisan_bunrui_chk[120]": "1", "zaisan_bunrui_chk[130]": "1",
        "zaisan_bunrui_chk[190]": "1", "zaisan_bunrui_chk[999]": "1",
    }
    url = "https://www.koubai.nta.go.jp/auctionx/public/hp0241.php"
    res = session.get(url, params=params, timeout=TIMEOUT)
    print(f"  HTTP {res.status_code} / {len(res.text):,}文字 / {res.url}")
    soup = BeautifulSoup(res.text, "html.parser")
    # 物件行らしき要素: 詳細ページへのリンクを持つ塊を探す
    detail_links = [a for a in soup.find_all("a", href=True)
                    if "hp024" in a["href"] and "hp0241" not in a["href"]]
    print(f"  詳細リンク候補: {len(detail_links)}件 (先頭5件):")
    for a in detail_links[:5]:
        print(f"    [{a.get_text(' ', strip=True)[:50]}] {a['href']}")
    # 価格表記の周辺構造を見る (物件カードのタグ構成を知る)
    for i, node in enumerate(soup.find_all(string=re.compile("見積価額"))[:3]):
        parent = node.find_parent(["tr", "li", "div", "dl"])
        if parent:
            print(f"  「見積価額」周辺[{i}] <{parent.name} class={parent.get('class')}>:")
            text = parent.get_text(" | ", strip=True)[:300]
            print(f"    {text}")
    # ページャの形
    pager = [a["href"] for a in soup.find_all("a", href=True)
             if re.search(r"page|Page|頁", a["href"] + a.get_text())]
    print(f"  ページャ候補: {pager[:5]}")


def recon_ksi(session: requests.Session) -> None:
    """KSI: robots.txt が許可する /search/real-estate/ のデータ実体を見る。"""
    section("KSI官公庁オークション 不動産一覧")
    url = "https://kankocho.jp/search/real-estate/"
    res = session.get(url, timeout=TIMEOUT)
    print(f"  HTTP {res.status_code} / {len(res.text):,}文字")
    soup = BeautifulSoup(res.text, "html.parser")
    # 物件詳細リンク
    item_links = [a for a in soup.find_all("a", href=True)
                  if re.match(r"^/items/\d+/?$", a["href"])]
    print(f"  /items/ リンク: {len(item_links)}件 (先頭5件):")
    for a in item_links[:5]:
        print(f"    [{a.get_text(' ', strip=True)[:70]}] {a['href']}")
    if item_links:
        # 1件目のカード構造 (親を2段のぼってテキスト全体を見る)
        card = item_links[0]
        for _ in range(3):
            if card.parent:
                card = card.parent
        print(f"  カード構造サンプル <{card.name} class={card.get('class')}>:")
        print("    " + card.get_text(" | ", strip=True)[:400])
    # __NEXT_DATA__ or RSCペイロード
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd:
        print(f"  __NEXT_DATA__: あり ({len(nd.string or ''):,}文字)")
        try:
            data = json.loads(nd.string)
            print(f"    先頭キー: {list(data.keys())}")
        except Exception as e:
            print(f"    JSON解析失敗: {e}")
    else:
        print("  __NEXT_DATA__: なし (RSC形式)")
        # RSCのself.__next_f内に物件JSONが埋まっているか
        hits = res.text.count("__next_f")
        kag = res.text.count("鹿児島")
        print(f"  __next_f 出現: {hits}回 / 「鹿児島」出現: {kag}回")
        m = re.search(r".{80}鹿児島.{160}", res.text)
        if m:
            print(f"  「鹿児島」周辺サンプル: {m.group(0)[:280]!r}")
    # ページ数の手がかり
    total = re.search(r"(\d+)\s*件", soup.get_text(" ", strip=True))
    if total:
        print(f"  件数表記: {total.group(0)}")


def recon_bit(session: requests.Session) -> None:
    """BIT: 鹿児島の競売物件検索 (POST) が requests で通るか確かめる。"""
    section("BIT 裁判所競売 鹿児島POST検索")
    top = session.get("https://www.bit.courts.go.jp/app/top/pt001/h01",
                      timeout=TIMEOUT)
    print(f"  トップ: HTTP {top.status_code} / {len(top.text):,}文字")
    # HTML内の「鹿児島」周辺から prefecturesId/courtId の対応を探す
    for m in list(re.finditer(r".{120}鹿児島.{120}", top.text))[:4]:
        print(f"  「鹿児島」周辺: {m.group(0)!r}")
    cookies_before = len(session.cookies)
    res = session.post(
        "https://www.bit.courts.go.jp/app/top/pt001/h02",
        data={"prefecturesId": "46", "courtId": "", "saleScdId": "",
              "saleCls": "", "blockCls": "", "tabId": ""},
        timeout=TIMEOUT)
    print(f"  POST h02 (prefecturesId=46): HTTP {res.status_code} / "
          f"{len(res.text):,}文字 / 最終URL: {res.url} / "
          f"cookie {cookies_before}→{len(session.cookies)}個")
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "(なし)"
    print(f"  <title>: {title}")
    # 物件らしき塊 (事件番号=ケース番号の形式「令和◯年(ケ)第◯号」を探す)
    cases = re.findall(r"令和\d+年\s*[（(].[)）]\s*第\s*\d+\s*号", res.text)
    print(f"  事件番号らしき表記: {len(cases)}件 (例: {cases[:3]})")
    forms = soup.find_all("form")
    print(f"  応答内フォーム: {len(forms)}個: "
          f"{[(f.get('action'), f.get('method')) for f in forms[:6]]}")
    err = soup.find(string=re.compile("エラー|セッション|不正"))
    if err:
        print(f"  エラー文言: {err.strip()[:100]}")


def recon_pref(session: requests.Session) -> None:
    """鹿児島県 公売情報の現行URLと、県有財産売却ページを見る。"""
    for label, url in [
        ("鹿児島県 公売情報 index",
         "https://www.pref.kagoshima.jp/kurashi-kankyo/zei/koubai/index.html"),
        ("鹿児島県 県有財産売却",
         "https://www.pref.kagoshima.jp/kensei/nyusatu/zaisan/index.html"),
    ]:
        section(label)
        try:
            res = session.get(url, timeout=TIMEOUT)
        except Exception as e:
            print(f"  ❌ 取得失敗: {e}")
            continue
        print(f"  HTTP {res.status_code} / {len(res.text):,}文字 / {res.url}")
        if res.status_code != 200:
            continue
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "(なし)"
        print(f"  <title>: {title}")
        main = soup.find("main") or soup
        links = [(a.get_text(" ", strip=True)[:50], a["href"])
                 for a in main.find_all("a", href=True)
                 if any(k in a.get_text() for k in
                        ("公売", "売却", "オークション", "入札", "物件"))]
        print(f"  関連リンク {len(links)}件 (先頭12件):")
        for text, href in links[:12]:
            print(f"    [{text}] {href}")
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
    print("\n===== 偵察第2弾 完了 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
