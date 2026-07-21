"""スクレイパーレジストリ。config.yaml の type からアダプタを解決する。"""
from __future__ import annotations

from .base import BaseScraper
from .demo import DemoScraper
from .generic_html import GenericHtmlScraper
from .mailbox import GmailImapScraper
from .rss_feed import RssScraper
from .sumai_akiya import SumaiAkiyaScraper

REGISTRY: dict[str, type[BaseScraper]] = {
    "demo": DemoScraper,
    "generic_html": GenericHtmlScraper,
    "gmail_imap": GmailImapScraper,
    "rss": RssScraper,
    "sumai_akiya": SumaiAkiyaScraper,
}


def build_scraper(source_config: dict) -> BaseScraper:
    type_ = source_config.get("type", "generic_html")
    cls = REGISTRY.get(type_)
    if cls is None:
        raise ValueError(f"未知のスクレイパー type: {type_}")
    return cls(source_config)
