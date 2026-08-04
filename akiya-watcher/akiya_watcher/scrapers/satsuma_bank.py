"""さつま町 空き家情報バンク(売買)アダプタ。

ページ構造 (2026-07 GitHub Actions で実地確認):
    <h2><span class="bg"><span class="bg2"><span class="bg3">No.186 【売買】</span>...</h2>
    <p class="file-link-item"><a class="pdf" href="//.../No186r.pdf">No.186 (PDF...)</a></p>
    <figure class="img-item"><img src="..."/></figure>
    <div class="wysiwyg">
      <p>場所：宮之城屋地</p>
      <p>売買：480万円</p>                          ← 「価格：」表記の物件もある
      <p>問い合わせ：白石商事（0996-53-1775）</p>
      <p>備考：...</p>
    </div>
  が h2 ごとにフラットに並ぶ。値下げ物件は
    <p>売買：<strong>200万円</strong>（2025年6月2日、380万円から変更。)</p>
  のように旧価格が明示されるので advertised_previous_price_yen に載せる
  (初回取得でも値下げバッジが付く、Sumai空き家と同じ扱い)。

robots.txt は存在しない(404)ことを確認済み。巡回は BaseScraper の
最短アクセス間隔に従う。物件IDは「No.163」の番号から作る
(PDFファイル名は値下げ改版で No163→No163R のように変わるため使わない)。
"""
from __future__ import annotations

from io import BytesIO
import re
import unicodedata
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

from ..criteria import parse_area_sqm, parse_parking_slots, parse_price_yen
from ..models import Listing
from .base import BaseScraper

_HEAD = re.compile(r"N[Oo]\.?\s*(\d+)")
_PREV_PRICE = re.compile(r"([0-9,]+(?:\.[0-9]+)?)\s*万円?\s*から(?:変更|値下げ)")
_LAYOUT = re.compile(r"間取り\s*[:：]?\s*([0-9]+\s*(?:S?LDK|DK|K|R)(?:\s*\+\s*S)?)",
                     re.IGNORECASE)
_MAX_PDF_BYTES = 10 * 1024 * 1024


def _normalize_pdf_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", "", text)


def _labeled_area(text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        match = re.search(
            rf"(?:{label})\s*[:：]?\s*([0-9,]+(?:\.[0-9]+)?)"
            r"\s*(?:㎡|m2|平米|平方メートル)",
            text, re.IGNORECASE,
        )
        if match:
            return parse_area_sqm(match.group(0))
    return None


def parse_pdf_details(text: str) -> dict:
    """物件PDFの抽出文字列から、判断に必要な項目だけを読む。"""
    normalized = _normalize_pdf_text(text)
    layout_match = _LAYOUT.search(normalized)
    return {
        "layout": re.sub(r"\s+", "", layout_match.group(1)).upper()
        if layout_match else "",
        "parking_slots": parse_parking_slots(normalized),
        "land_area_sqm": _labeled_area(
            normalized, ("土地面積", "敷地面積", "宅地面積")),
        "floor_area_sqm": _labeled_area(
            normalized, ("延床面積", "建物面積", "床面積")),
    }


def _extract_pdf_text(content: bytes) -> str:
    if len(content) > _MAX_PDF_BYTES:
        raise ValueError("PDFが10MBを超えています")
    reader = PdfReader(BytesIO(content))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(chunks)


def _detail_summary(data: dict) -> str:
    parts: list[str] = []
    if data.get("layout"):
        parts.append(f"間取り {data['layout']}")
    if data.get("parking_slots") is not None:
        parts.append(f"駐車 {data['parking_slots']}台")
    if data.get("land_area_sqm") is not None:
        parts.append(f"土地 {data['land_area_sqm']:g}㎡")
    if data.get("floor_area_sqm") is not None:
        parts.append(f"建物 {data['floor_area_sqm']:g}㎡")
    return "PDF詳細: " + " / ".join(parts) if parts else ""


class SatsumaBankScraper(BaseScraper):
    source_id = "satsuma_bank"

    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config.get("id", self.source_id)
        self.list_url = config["list_url"]

    def fetch_listings(self) -> list[Listing]:
        res = self.get(self.list_url)
        res.encoding = res.apparent_encoding
        return self.parse(res.text)

    def enrich_listing(self, listing: Listing) -> Listing:
        """新着・掲載変更時だけ呼ばれ、リンク先PDFの判断材料を追加する。"""
        if not urlsplit(listing.url).path.lower().endswith(".pdf"):
            return listing
        response = self.get(listing.url)
        details = parse_pdf_details(_extract_pdf_text(response.content))
        return self.apply_enrichment(listing, details)

    @staticmethod
    def export_enrichment(listing: Listing) -> dict:
        return dict(listing.raw.get("pdf_details", {}))

    @staticmethod
    def apply_enrichment(listing: Listing, data: dict) -> Listing:
        for name in ("layout", "parking_slots", "land_area_sqm", "floor_area_sqm"):
            value = data.get(name)
            if value not in (None, ""):
                setattr(listing, name, value)
        summary = _detail_summary(data)
        if summary and summary not in listing.description:
            listing.description = " / ".join(
                part for part in (listing.description, summary) if part)
        listing.raw["pdf_details"] = dict(data)
        return listing

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        listings: list[Listing] = []
        for h2 in soup.find_all("h2"):
            head = h2.get_text(" ", strip=True)
            m = _HEAD.search(head)
            if m is None:
                continue
            number = m.group(1)

            # 次の物件見出しまでの兄弟要素がこの物件のブロック
            pdf_url = ""
            lines: list[str] = []
            for sib in h2.find_next_siblings():
                if sib.name == "h2":
                    break
                a = sib.select_one("a.pdf") if hasattr(sib, "select_one") else None
                if a is not None and not pdf_url:
                    href = a.get("href", "")
                    if href.startswith("//"):
                        href = "https:" + href
                    pdf_url = href
                if "wysiwyg" in (sib.get("class") or []):
                    for p in sib.find_all("p"):
                        text = " ".join(p.get_text(" ", strip=True).split())
                        if text:
                            lines.append(text)

            # 「場所：」等のラベルで区切る。通常は1ラベル=1つの<p>だが、
            # No.67 のように1段落へ全ラベルが詰め込まれた物件もあるため、
            # 行単位ではなく全文をラベルで分割して読む
            blob = "\n".join(lines)
            parts = re.split(r"(場所|売買|価格|問い合わせ|備考)\s*：", blob)
            fields: dict[str, str] = {}
            for key, value in zip(parts[1::2], parts[2::2]):
                fields.setdefault(key, " ".join(value.split()).strip())

            place = fields.get("場所", "")
            price_line = fields.get("売買") or fields.get("価格") or ""
            prev = _PREV_PRICE.search(price_line)
            prev_yen = parse_price_yen(prev.group(1) + "万円") if prev else None
            # 現価格は行頭側に来る。「から変更」以降を落としてから読む
            current_part = price_line.split("から変更")[0]
            current_part = _PREV_PRICE.sub("", current_part) or price_line
            price_yen = parse_price_yen(current_part)

            description = " / ".join(
                v for v in [fields.get("備考", ""), fields.get("問い合わせ", ""),
                            price_line if prev else ""] if v)

            listings.append(Listing(
                source=self.source_id,
                listing_id=f"satsuma-{number}",
                title=f"さつま町空き家バンク No.{number}（{place or '場所不明'}）{head[m.end():].strip()}",
                url=pdf_url or self.list_url,
                price_yen=price_yen,
                address=f"鹿児島県薩摩郡さつま町{place}",
                description=description,
                advertised_previous_price_yen=prev_yen,
                raw={"head": head, **fields},
            ))
        return listings
