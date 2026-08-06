"""実地検証: いちき串木野市の公式一覧とアットホーム一覧を統合して読む。"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers import build_scraper  # noqa: E402


def main() -> None:
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    source = next(item for item in config["sources"]
                  if item["id"] == "ichikikushikino_akiya_bank")
    scraper = build_scraper(source)
    official_url = source["official_url"]
    print(f"robots.txt判定: {'許可' if scraper._allowed_by_robots(official_url) else '禁止'}")

    listings = scraper.fetch_listings()
    previews = [item for item in listings if item.listing_id.startswith("city-")]
    under_limit = [item for item in listings
                   if item.price_yen is None or item.price_yen <= 3_000_000]
    linked = [item for item in listings if item.raw.get("official_number")]
    print(f"統合結果: {len(listings)}件 / 300万円以下・準備中: {len(under_limit)}件")
    print(f"市公式との照合済み: {len(linked)}件 / 先行掲載: {len(previews)}件")
    for item in previews:
        print(f"先行掲載: {item.listing_id} / {item.price_yen or '価格準備中'} / {item.title}")

    if len(listings) < 20:
        raise SystemExit("通常掲載を20件以上取得できませんでした")
    if len(listings) > 25 or len(previews) > 5:
        raise SystemExit("公式一覧とアットホーム一覧が重複している可能性があります")
    if len(linked) < 10:
        raise SystemExit("市公式一覧とアットホーム一覧を十分に照合できませんでした")
    print("判定: OK")


if __name__ == "__main__":
    main()
