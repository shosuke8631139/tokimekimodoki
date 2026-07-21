"""接続テスト第5弾その2: 官報の利用条件と代替手段の確認。

第1弾の結果: robots.txt が /20 (=日付ページ全部) を自動取得禁止にしていた。
今回の確認事項:
  1. 利用案内(guidance.html)・FAQの本文 → 転載・二次利用・自動取得の規定
  2. RSS/フィードなど機械向けの公式窓口があるか
  3. 号外の目次ページ(裁判所公告の載る場所)を「人間として1回だけ」見て、
     公告がテキストで載っているか、ページ内の構造を確認する
     (自動巡回の設計判断のための一度きりの下見。巡回はしない)
"""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (personal research; one-time manual check)"}
WAIT = 3.0
BASE = "https://www.kanpo.go.jp"


def fetch(url: str, timeout: int = 20) -> requests.Response | None:
    time.sleep(WAIT)
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        print(f"  GET {url} -> {r.status_code} "
              f"({r.headers.get('Content-Type', '?')}, {len(r.content):,} bytes)")
        r.encoding = r.apparent_encoding or r.encoding
        return r
    except Exception as e:
        print(f"  GET {url} -> 失敗 {type(e).__name__}: {e}")
        return None


def to_text(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text)


print("===== 1. 利用案内とFAQの本文 =====")
for path in ("/guidance.html", "/faq.html"):
    r = fetch(BASE + path)
    if r is not None and r.status_code == 200:
        text = to_text(r.text)
        print(f"  --- {path} 本文 (先頭4000文字) ---")
        print("  " + text[:4000])
        print("  --- キーワード出現 ---")
        for kw in ("転載", "複製", "二次利用", "自動", "クローラ", "ロボット",
                   "プログラム", "API", "RSS", "ダウンロード", "リンク", "著作権"):
            print(f"    「{kw}」: {text.count(kw)}回")

print("\n===== 2. 機械向け窓口の有無 =====")
for path in ("/rss.xml", "/feed", "/index.rdf", "/sitemap.xml", "/data/", "/api/"):
    fetch(BASE + path)

print("\n===== 3. 号外の全体目次を一度だけ下見 (自動巡回はしない) =====")
r = fetch(f"{BASE}/20260721/20260721.fullcontents.html")
if r is not None and r.status_code == 200:
    text = to_text(r.text)
    print(f"  本文文字数: {len(text)}")
    for kw in ("裁判所", "公告", "相続", "清算", "会社"):
        print(f"  「{kw}」出現: {text.count(kw)}回")
    idx = text.find("裁判所")
    if idx >= 0:
        print("  「裁判所」周辺400文字:")
        print("  " + text[max(0, idx - 100):idx + 300])
    # 目次からリンク構造も観察
    hrefs = re.findall(r'href="([^"]+)"', r.text)
    court = [h for h in hrefs if "sai" in h or "kokoku" in h][:10]
    print(f"  裁判所らしきリンク: {court}")
    print(f"  リンク例(先頭15件): {hrefs[:15]}")

print("\n===== テスト終了 =====")
