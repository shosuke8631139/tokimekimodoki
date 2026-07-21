"""接続テスト第4弾: アットホーム空き家バンク共通システムの自治体を探索。

サブドメインは <県名ローマ字>-c<自治体コード>.akiya-athome.jp の形式
(鹿児島市 = kagoshima-c46201 で確認済み)。対象市町のコードで一斉確認し、
稼働している自治体を特定する。あわせて鹿児島市ページのHTML構造を採取して
読み取り部品(アダプタ)の設計材料にする。
"""
import sys

sys.path.insert(0, ".")

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "akiya-watcher/0.1 (personal use)"}

# (表示名, サブドメイン)
CANDIDATES = [
    ("鹿児島市", "kagoshima-c46201"),
    ("鹿屋市", "kagoshima-c46203"),
    ("出水市", "kagoshima-c46208"),
    ("垂水市", "kagoshima-c46214"),
    ("薩摩川内市", "kagoshima-c46215"),
    ("日置市", "kagoshima-c46216"),
    ("曽於市", "kagoshima-c46217"),
    ("霧島市", "kagoshima-c46218"),
    ("いちき串木野市", "kagoshima-c46219"),
    ("南さつま市", "kagoshima-c46220"),
    ("志布志市", "kagoshima-c46221"),
    ("南九州市", "kagoshima-c46223"),
    ("伊佐市", "kagoshima-c46224"),
    ("姶良市", "kagoshima-c46225"),
    ("さつま町", "kagoshima-c46392"),
    ("湧水町", "kagoshima-c46452"),
    ("大崎町", "kagoshima-c46468"),
    ("東串良町", "kagoshima-c46482"),
    ("南大隅町", "kagoshima-c46491"),
    ("肝付町", "kagoshima-c46492"),
    ("宮崎市", "miyazaki-c45201"),
    ("都城市", "miyazaki-c45202"),
    ("小林市", "miyazaki-c45205"),
    ("えびの市", "miyazaki-c45209"),
]

print("===== 1. 稼働自治体の探索 =====")
alive = []
for name, sub in CANDIDATES:
    url = f"https://{sub}.akiya-athome.jp/"
    try:
        r = requests.get(url, timeout=12, headers=UA)
        hits = r.text.count("万円")
        mark = "✅" if r.status_code == 200 and hits > 0 else "△"
        print(f"  {mark} {name}: status {r.status_code}, 価格表記 {hits}箇所")
        if r.status_code == 200 and hits > 0:
            alive.append((name, url))
    except Exception as e:
        print(f"  ❌ {name}: {type(e).__name__}")

print(f"\n稼働確認: {len(alive)}自治体")

print("\n===== 2. 鹿児島市ページのHTML構造採取 =====")
try:
    r = requests.get("https://kagoshima-c46201.akiya-athome.jp/", timeout=15, headers=UA)
    soup = BeautifulSoup(r.text, "html.parser")
    # 「万円」を含む要素の親をたどり、物件カードらしき構造を観察する
    price_nodes = [t for t in soup.find_all(string=lambda s: s and "万円" in s)][:3]
    for i, node in enumerate(price_nodes, 1):
        chain = []
        el = node.parent
        for _ in range(5):
            if el is None:
                break
            cls = ".".join(el.get("class", [])) if el.get("class") else ""
            chain.append(f"{el.name}[{cls}]")
            el = el.parent
        print(f"  価格{i}: 「{str(node).strip()[:30]}」 親: {' < '.join(chain)}")
    # 物件詳細へのリンクのパターン
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    bukken_links = [h for h in links if "bukken" in h or "detail" in h or "estate" in h][:8]
    print(f"  物件らしきリンク例: {bukken_links}")
    # 最初の価格ノード周辺のHTML断片
    if price_nodes:
        card = price_nodes[0].parent
        for _ in range(3):
            if card.parent is not None:
                card = card.parent
        print("  --- カード断片 (先頭1200文字) ---")
        print(str(card)[:1200])
except Exception as e:
    print(f"  構造採取失敗: {type(e).__name__}: {e}")

print("\n===== テスト終了 =====")
