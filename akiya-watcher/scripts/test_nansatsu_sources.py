"""GitHub Actions用。通知・本番DB・個人情報の出力を伴わない接続検証。"""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from akiya_watcher.scrapers import build_scraper


def check(source):
    scraper = build_scraper(source)
    items = scraper.fetch_listings()
    assert scraper.full_snapshot, f"{source['id']}: 一部ページ取得失敗"
    assert items, f"{source['id']}: 取得0件"
    assert len({x.uid for x in items}) == len(items)
    priced = [x for x in items if x.price_yen is not None]
    assert priced, f"{source['id']}: 価格を読めた物件0件"
    under = [x for x in priced if x.price_yen <= 3_000_000]
    print(f"OK {source['id']}: 全{len(items)}件 / 価格あり{len(priced)}件 / 300万円以下{len(under)}件", flush=True)


if __name__ == '__main__':
    config = yaml.safe_load(Path('config.yaml').read_text(encoding='utf-8'))
    sources = [s for s in config['sources'] if s['type'] in {'nansatsu_city', 'minamisatsuma_bank'}]
    assert len(sources) == 4
    # 別ホストだけ並行取得。同一ホストの10秒間隔はBaseScraperに従う。
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(check, sources))
