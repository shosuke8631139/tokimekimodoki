"""スクレイパーレジストリ。config.yaml の type からアダプタを解決する。"""
from __future__ import annotations

from .base import BaseScraper
from .demo import DemoScraper
from .generic_html import GenericHtmlScraper
from .hioki_bank import HiokiBankScraper
from .ichikikushikino_bank import IchikikushikinoBankScraper
from .ksi_auction import KsiAuctionScraper
from .mailbox import GmailImapScraper
from .minamisatsuma_bank import MinamisatsumaBankScraper
from .miyakonojo_bank import MiyakonojoBankScraper
from .kirishima_bank import KirishimaBankScraper
from .nta_koubai import NtaKoubaiScraper
from .pref_kagoshima_sale import PrefKagoshimaSaleScraper
from .rss_feed import RssScraper
from .satsuma_bank import SatsumaBankScraper
from .satsumasendai_city import SatsumasendaiCityScraper
from .sumai_akiya import SumaiAkiyaScraper
from .watch import WatchScraper
from .yusui_bank import YusuiBankScraper

from .nansatsu_city import NansatsuCityScraper

REGISTRY: dict[str, type[BaseScraper]] = {
    "nansatsu_city": NansatsuCityScraper,
    "demo": DemoScraper,
    "generic_html": GenericHtmlScraper,
    "gmail_imap": GmailImapScraper,
    "hioki_bank": HiokiBankScraper,
    "ichikikushikino_bank": IchikikushikinoBankScraper,
    "kirishima_bank": KirishimaBankScraper,
    "ksi_auction": KsiAuctionScraper,
    "minamisatsuma_bank": MinamisatsumaBankScraper,
    "miyakonojo_bank": MiyakonojoBankScraper,
    "nta_koubai": NtaKoubaiScraper,
    "pref_kagoshima_sale": PrefKagoshimaSaleScraper,
    "rss": RssScraper,
    "satsuma_bank": SatsumaBankScraper,
    "satsumasendai_city": SatsumasendaiCityScraper,
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
