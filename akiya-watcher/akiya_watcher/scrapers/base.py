"""スクレイパー基底クラス。

礼儀正しい取得(robots.txt 尊重・リクエスト間隔・UA明示)を共通化する。
各サイトのアダプタは fetch_listings() を実装して Listing のリストを返す。
"""
from __future__ import annotations

import time
import urllib.robotparser
from abc import ABC, abstractmethod
from urllib.parse import urlparse

import requests

from ..models import Listing

USER_AGENT = "akiya-watcher/0.1 (personal use; contact: set-your-email)"
MIN_INTERVAL_SEC = 10.0   # 同一ホストへの最短アクセス間隔


class BaseScraper(ABC):
    source_id: str = "base"

    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_fetch: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    @abstractmethod
    def fetch_listings(self) -> list[Listing]:
        """条件検索結果ページ等を取得し、Listing に正規化して返す。"""

    # ------------------------------------------------------------ 共通処理

    def _allowed_by_robots(self, url: str) -> bool:
        host = urlparse(url).netloc
        rp = self._robots.get(host)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{urlparse(url).scheme}://{host}/robots.txt")
            try:
                rp.read()
            except Exception:
                # robots.txt が読めない場合は保守的に許可扱いにせず記録だけ残す
                print(f"[warn] robots.txt 取得失敗: {host} (続行)")
            self._robots[host] = rp
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    def get(self, url: str) -> requests.Response:
        """robots.txt を尊重し、ホスト毎に間隔を空けて GET する。"""
        if not self._allowed_by_robots(url):
            raise PermissionError(f"robots.txt により取得禁止: {url}")
        host = urlparse(url).netloc
        elapsed = time.time() - self._last_fetch.get(host, 0.0)
        if elapsed < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - elapsed)
        res = self.session.get(url, timeout=30)
        self._last_fetch[host] = time.time()
        res.raise_for_status()
        return res
