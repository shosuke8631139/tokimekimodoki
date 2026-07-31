"""空き家バンク利用登録の手続き偵察 (霧島市・鹿屋市・都城市・さつま町)。

各市町の案内ページを取得して、
  1. ページ本文(整形テキスト)
  2. 様式・申込書・誓約書らしきリンク一覧
をログに出す。DB・通知は使わない読み取り専用テスト。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) akiya-watcher source test"

TARGETS = [
    ("霧島市 利用希望の方", "https://www.city-kirishima.jp/kyodo/shise/ijuteju/akiya/akiyabankriyoukibounokata.html"),
    ("鹿屋市 利用登録", "https://www.city.kanoya.lg.jp/iju/akiyabank/riyoutouroku.html"),
    ("鹿屋市 借りたい・買いたい", "https://www.city.kanoya.lg.jp/iju/akiyabank/karirukau.html"),
    ("都城市 空き家バンク トップ", "https://www.city.miyakonojo.miyazaki.jp/site/akiyabank/"),
    ("都城市 制度ページ(旧CMS)", "http://cms.city.miyakonojo.miyazaki.jp/display.php?cont=150716234546"),
    ("さつま町 空き家情報バンク(売買)", "https://www.satsuma-net.jp/teiju/akiya/1/5623.html"),
    ("さつま町 制度ページ", "https://www.satsuma-net.jp/soshiki/yakuba/1013/1_1/ijuteiju_site/akiya/akiya_seido/5664.html"),
]

FORM_PAT = re.compile(r"様式|申込|申請|登録|誓約|利用|カード", re.I)
FILE_PAT = re.compile(r"\.(pdf|docx?|xlsx?)($|\?)", re.I)


def dump(label: str, url: str) -> None:
    print("=" * 78)
    print(f"### {label}")
    print(f"URL: {url}")
    try:
        res = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        res.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - 偵察用途なので握って報告
        print(f"!! 取得失敗: {exc}")
        return
    res.encoding = res.apparent_encoding
    soup = BeautifulSoup(res.text, "html.parser")

    print("--- 様式・申請らしきリンク ---")
    seen = set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        href = urljoin(url, a["href"])
        if href in seen:
            continue
        if FILE_PAT.search(href) or FORM_PAT.search(text):
            seen.add(href)
            print(f"  [{text[:60]}] {href}")

    print("--- 本文テキスト(先頭6000字) ---")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = "\n".join(
        line for line in (l.strip() for l in soup.get_text("\n").splitlines()) if line
    )
    print(text[:6000])


def main() -> None:
    for label, url in TARGETS:
        dump(label, url)
    print("=" * 78)
    print("偵察おわり")


if __name__ == "__main__":
    main()
