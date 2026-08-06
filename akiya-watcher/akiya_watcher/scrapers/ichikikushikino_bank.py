"""いちき串木野市の公式一覧とアットホーム一覧を重複なく統合する。

公式ページには価格・建物面積・成約状態に加え、アットホーム一覧へ出る前の
「準備中」物件が載る。通常掲載は既存のアットホーム一覧から詳しく読み、
公式ページだけにある物件を補うことで、二重通知せず早く見つける。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..criteria import parse_area_sqm, parse_price_yen
from ..models import Listing
from .generic_html import GenericHtmlScraper

_NUMBER = re.compile(r"N[Oo]\.?\s*(\d+)", re.IGNORECASE)


@dataclass
class OfficialListing:
    number: str
    district: str
    built: str
    floor_area_sqm: float | None
    price_yen: int | None
    status: str
    detail_url: str
    pdf_url: str

    @property
    def sold(self) -> bool:
        return "成約" in self.status


def _url_key(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


class IchikikushikinoBankScraper(GenericHtmlScraper):
    source_id = "ichikikushikino_bank"
    # 「準備中」は価格不明でも大事な先行情報なので、応相談カットの対象にしない。
    prices_reliable = False

    def __init__(self, config: dict):
        super().__init__(config)
        self.official_url = config["official_url"]

    def fetch_listings(self) -> list[Listing]:
        response = self.get(self.official_url)
        response.encoding = response.apparent_encoding
        official = self.parse_official(response.text)
        athome = super().fetch_listings()
        return self.merge_listings(athome, official)

    def parse_official(self, html: str) -> list[OfficialListing]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[OfficialListing] = []
        for row in soup.select("table tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) != 8:
                continue
            title = " ".join(cells[0].get_text(" ", strip=True).split())
            match = _NUMBER.search(title)
            transaction = cells[4].get_text(" ", strip=True)
            if match is None or "売買" not in transaction:
                continue
            status = " ".join(cells[5].get_text(" ", strip=True).split())
            detail = cells[0].find("a", href=True)
            pdf = cells[7].find("a", href=True)
            area_text = cells[3].get_text(" ", strip=True)
            records.append(OfficialListing(
                number=match.group(1),
                district=cells[1].get_text(" ", strip=True),
                built=cells[2].get_text(" ", strip=True),
                floor_area_sqm=parse_area_sqm(area_text + "㎡"),
                price_yen=parse_price_yen(status),
                status=status,
                detail_url=urljoin(self.official_url, detail["href"]) if detail else "",
                pdf_url=urljoin(self.official_url, pdf["href"]) if pdf else "",
            ))
        return records

    def merge_listings(self, athome: list[Listing],
                       official: list[OfficialListing]) -> list[Listing]:
        by_url = {_url_key(record.detail_url): record
                  for record in official if record.detail_url}
        matched_numbers: set[str] = set()

        for listing in athome:
            record = by_url.get(_url_key(listing.url))
            if record is None:
                continue
            matched_numbers.add(record.number)
            if record.price_yen is not None:
                listing.price_yen = record.price_yen
            if listing.floor_area_sqm is None:
                listing.floor_area_sqm = record.floor_area_sqm
            if not listing.address and record.district:
                listing.address = f"鹿児島県いちき串木野市{record.district}"
            official_note = f"市公式No.{record.number} / 建築年 {record.built}"
            if official_note not in listing.description:
                listing.description = " / ".join(
                    part for part in (listing.description, official_note) if part)
            listing.raw["official_number"] = record.number
            listing.raw["official_pdf_url"] = record.pdf_url

        # アットホーム一覧にまだ出ていない「準備中」や市独自掲載だけを補う。
        for record in official:
            if record.sold or record.number in matched_numbers:
                continue
            status = record.status or "価格不明"
            description = f"市公式ページ先行掲載 / 状態 {status} / 建築年 {record.built}"
            athome.append(Listing(
                source=self.source_id,
                listing_id=f"city-{record.number}",
                title=(f"いちき串木野市空き家バンク No.{record.number}"
                       f"（{record.district or '地区不明'}・{status}）"),
                url=record.detail_url or record.pdf_url or self.official_url,
                price_yen=record.price_yen,
                address=f"鹿児島県いちき串木野市{record.district}",
                floor_area_sqm=record.floor_area_sqm,
                description=description,
                raw={
                    "official_number": record.number,
                    "official_pdf_url": record.pdf_url,
                    "official_status": status,
                },
            ))
        return athome
