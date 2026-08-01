"""巡回先拡張の偵察: 姶良市(アットホーム共通システム想定)+湧水町(町独自ページ)。

30分圏の監視の穴を埋める (2026-08-02)。読み取り専用テスト。
1. 姶良市: aira-c46225.akiya-athome.jp が鹿児島市と同じセレクタで読めるか確認。
2. 湧水町: 空家バンクページの構造をダンプして、アダプタが書けるか調べる。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.generic_html import GenericHtmlScraper  # noqa: E402

ATHOME_FIELDS = {
    "title":       {"selector": ".property-name a", "attr": "text"},
    "url":         {"selector": ".property-name a", "attr": "href"},
    "price":       {"selector": "dl.bukken-info dd.price-strong", "attr": "text"},
    "layout":      {"selector": "dl.bukken-info dd:nth-of-type(2)", "attr": "text"},
    "land_area":   {"selector": "dl.bukken-info dd:nth-of-type(3)", "attr": "text"},
    "address":     {"selector": "dl.bukken-info dd:nth-of-type(4)", "attr": "text"},
    "description": {"selector": "dl.bukken-info", "attr": "text"},
}

AIRA_URL = "https://aira-c46225.akiya-athome.jp/"
YUSUI_AKIYA = "https://www.town.yusui.kagoshima.jp/soshiki/34/787.html"
YUSUI_AKICHI = "https://www.town.yusui.kagoshima.jp/soshiki/34/789.html"

UA = {"User-Agent": "akiya-watcher/0.1 (structure test)"}


def robots(base: str) -> None:
    try:
        res = requests.get(base.rstrip("/") + "/robots.txt", timeout=20, headers=UA)
        print(f"robots.txt status={res.status_code}")
        print(res.text[:600])
    except Exception as exc:  # noqa: BLE001
        print(f"robots.txt 取得失敗: {exc}")


def test_aira() -> None:
    print("=" * 78)
    print("### 姶良市 (アットホーム共通システム・一覧URL探し)")
    res = requests.get(AIRA_URL, timeout=30, headers=UA)
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")
    print(f"トップ status={res.status_code} bytes={len(res.text)}")
    print("--- トップの内部リンク一覧 ---")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = " ".join(a.get_text(" ", strip=True).split())[:30]
        if href.startswith("#") or href.startswith("mailto"):
            continue
        print(f"  [{text}] {href}")
        links.append(href)

    # 売買・賃貸の一覧候補URLを既存セレクタで試す
    candidates = ["/buy/live/area/", "/rent/live/area/", "/buy/", "/list/"]
    candidates += [h for h in links if re.search(r"buy|sale|rent|list|area", h)]
    seen = set()
    for path in candidates:
        url = path if path.startswith("http") else AIRA_URL.rstrip("/") + path
        if url in seen:
            continue
        seen.add(url)
        print(f"--- 候補 {url} ---")
        scraper = GenericHtmlScraper({
            "id": "aira_akiya_bank",
            "list_url": url,
            "item_selector": "ul.property-simple > li",
            "fields": ATHOME_FIELDS,
        })
        try:
            listings = scraper.fetch_listings()
        except Exception as exc:  # noqa: BLE001
            print(f"  !! 取得失敗: {exc}")
            continue
        print(f"  property-simple読み取り: {len(listings)}件")
        for l in listings[:4]:
            price = f"{l.price_yen:,}円" if l.price_yen is not None else "価格不明"
            print(f"    {price} {l.address} | {l.title[:40]}")
            print(f"        {l.url}")
        if not listings:
            # 別のセレクタ候補を観察
            r2 = requests.get(url, timeout=30, headers=UA)
            r2.encoding = r2.apparent_encoding
            s2 = BeautifulSoup(r2.text, "html.parser")
            for el in s2.find_all(class_=re.compile("property|bukken|item|card"))[:8]:
                print(f"    <{el.name} class={el.get('class')}> "
                      f"{' '.join(el.get_text(' ', strip=True).split())[:60]}")
        if len(seen) >= 6:
            break


def recon_yusui(label: str, url: str) -> None:
    print("=" * 78)
    print(f"### 湧水町 {label} 構造偵察: {url}")
    try:
        res = requests.get(url, timeout=30, headers=UA)
    except Exception as exc:  # noqa: BLE001
        print(f"!! 取得失敗: {exc}")
        return
    res.encoding = res.apparent_encoding
    print(f"status={res.status_code} bytes={len(res.text)}")
    soup = BeautifulSoup(res.text, "html.parser")
    pat = re.compile(r"万円|物件|No|№|売買|賃貸|空家|空き家")
    seen = 0
    for el in soup.find_all(string=pat):
        parent = el.parent
        chain = []
        node = parent
        for _ in range(4):
            if node is None or node.name is None:
                break
            chain.append(f"{node.name}.{'.'.join(node.get('class', []) or [])}")
            node = node.parent
        text = " ".join(str(el).split())[:60]
        print(f"  [{text}] 祖先: {' < '.join(chain)}")
        seen += 1
        if seen >= 30:
            break
    # 物件エントリ(No.xxx)を含む<td>を丸ごとダンプして、リンク・住所・
    # 写真の持ち方を確認する (アダプタ設計のため)
    dumped = 0
    for strong in soup.find_all("strong"):
        text = " ".join(strong.get_text(" ", strip=True).split())
        if not re.match(r"No\.?\s*\d", text):
            continue
        td = strong.find_parent("td")
        if td is None:
            continue
        print(f"--- 物件エントリのtd全体 ({text[:30]}) ---")
        print(td.prettify()[:2500])
        dumped += 1
        if dumped >= 2:
            break
    print("--- 本文リンク全部 ---")
    for a in soup.find_all("a", href=True)[:60]:
        text = " ".join(a.get_text(" ", strip=True).split())[:40]
        print(f"  [{text}] {a['href']}")


def main() -> None:
    test_aira()
    recon_yusui("空家バンク", YUSUI_AKIYA)
    recon_yusui("空地バンク", YUSUI_AKICHI)
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
