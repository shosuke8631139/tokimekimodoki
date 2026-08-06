"""偵察: いちき串木野市の公式空き家一覧の表構造を最小アクセスで確認する。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers.generic_html import GenericHtmlScraper  # noqa: E402

URL = "https://www.city.ichikikushikino.lg.jp/seisaku1/akiyabank/akiya-bukkenn.html"


def main() -> None:
    scraper = GenericHtmlScraper({
        "id": "ichikikushikino_city_preview",
        "list_url": URL,
        "item_selector": "table tr",
        "fields": {},
    })
    print(f"robots.txt判定: {'許可' if scraper._allowed_by_robots(URL) else '禁止'}")
    response = scraper.get(URL)
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")

    rows: list[list[str]] = []
    for tr in soup.select("table tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split())
                 for cell in tr.find_all(["th", "td"])]
        joined = " | ".join(cells)
        if re.search(r"N[Oo]\.?.*?\d+", joined) and ("売買" in joined or "成約" in joined):
            rows.append(cells)

    print(f"売買・成約を含む物件行: {len(rows)}件")
    for cells in rows[:5]:
        safe = [re.sub(r"\d{2,4}-\d{2,4}-\d{3,4}", "[電話番号]", cell)
                for cell in cells]
        print(f"列数={len(cells)}: {safe}")
    if len(rows) < 10:
        raise SystemExit("物件表を十分に読めませんでした")


if __name__ == "__main__":
    main()
