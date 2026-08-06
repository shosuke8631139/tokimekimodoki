"""実地検証: 日置市No.228・254を一覧と詳細ページから重複なく追う。"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from akiya_watcher.scrapers import build_scraper  # noqa: E402


def main() -> None:
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    source = next(item for item in config["sources"]
                  if item["id"] == "hioki_akiya_bank")
    scraper = build_scraper(source)
    for watch in source["detail_watches"]:
        allowed = scraper._allowed_by_robots(watch["url"])
        print(f"robots.txt No.{watch['number']}: {'許可' if allowed else '禁止'}")
        if not allowed:
            raise SystemExit(f"No.{watch['number']} はrobots.txtで取得禁止です")

    listings = scraper.fetch_listings()
    by_number = {item.raw.get("number"): item for item in listings}
    expected_max = {"228": 2_000_000, "254": 1_500_000}
    for number, ceiling in expected_max.items():
        item = by_number.get(number)
        if item is None:
            raise SystemExit(f"No.{number} を一覧から取得できませんでした")
        print(f"追跡No.{number}: 統合価格={item.price_yen:,}円 / "
              f"詳細価格={item.raw.get('detail_watch_price_yen'):,}円 / URL={item.url}")
        if item.price_yen > ceiling:
            raise SystemExit(f"No.{number} の値下げ後価格を取得できていません")
        if item.raw.get("detail_watch_url") != item.url:
            raise SystemExit(f"No.{number} の一覧URLと詳細URLが一致しません")
    watched = [item for item in listings if item.raw.get("detail_watch_url")]
    if len(watched) != 2:
        raise SystemExit("指名2件が重複または欠落しています")
    print(f"日置市全体: {len(listings)}件 / 指名追跡: {len(watched)}件")
    print("判定: OK")


if __name__ == "__main__":
    main()
