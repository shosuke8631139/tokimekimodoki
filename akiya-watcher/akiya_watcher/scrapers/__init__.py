"""スクレイパーレジストリ。config.yaml の type からアダプタを解決する。"""
from __future__ import annotations

from .base import BaseScraper
from .demo import DemoScraper
from .generic_html import GenericHtmlScraper
from .mailbox import GmailImapScraper
from .miyakonojo_bank import MiyakonojoBankScraper
from .kirishima_bank import KirishimaBankScraper
from .rss_feed import RssScraper
from .satsuma_bank import SatsumaBankScraper
from .sumai_akiya import SumaiAkiyaScraper
from .watch import WatchScraper
from .yusui_bank import YusuiBankScraper

REGISTRY: dict[str, type[BaseScraper]] = {
    "demo": DemoScraper,
    "generic_html": GenericHtmlScraper,
    "gmail_imap": GmailImapScraper,
    "kirishima_bank": KirishimaBankScraper,
    "miyakonojo_bank": MiyakonojoBankScraper,
    "rss": RssScraper,
    "satsuma_bank": SatsumaBankScraper,
    "sumai_akiya": SumaiAkiyaScraper,
    "watch": WatchScraper,
    "yusui_bank": YusuiBankScraper,
}


def build_scraper(source_config: dict) -> BaseScraper:
    type_ = source_config.get("type", "generic_html")
    cls = REGISTRY.get(type_)
    if cls is None:
        raise ValueError(f"未知のスクレイパー type: {type_}")
    return cls(source_config)
