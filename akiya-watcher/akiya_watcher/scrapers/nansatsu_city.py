"""南九州・枕崎・指宿の市直営HTML。PDFや商用ポータルは取得しない。

全ページ・全詳細の取得成功後にのみ結果を返す。構造変更を0件と扱わない。
物件番号をIDに使い、見出しの「値下げ」は通知根拠にしない。
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models import Listing
from ..criteria import parse_area_sqm, parse_parking_slots


def text(node) -> str:
    return unicodedata.normalize("NFKC", node.get_text(" ", strip=True)) if node else ""


def fields(node) -> dict[str, str]:
    result = {}
    for row in node.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            result[re.sub(r"\s+", "", text(cells[0]))] = text(cells[1])
    return result


def price(value: str) -> int | None:
    """価格欄だけを渡す。複数価格の推測や家賃へのフォールバックはしない。"""
    value = unicodedata.normalize("NFKC", value)
    if re.search(r"応相談|要相談|相談|未定", value) and not re.search(r"\d", value):
        return None
    if "無償" in value:
        return 0
    matches = re.findall(r"([\d,]+(?:\.\d+)?)\s*(万円?|円)", value)
    if len(matches) != 1:
        raise ValueError(f"売却価格を一意に読めません: {value}")
    amount, unit = matches[0]
    return int(float(amount.replace(",", "")) * (10000 if unit.startswith("万") else 1))


class NansatsuCityScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self.source_id = config["id"]
        self.city = config["city"]
        self.list_url = config["list_url"]
        if self.city not in {"南九州市", "枕崎市", "指宿市"}:
            raise ValueError(f"未対応の市: {self.city}")

    def soup(self, url):
        response = self.get(url)
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        for old in soup.select("del, s, strike, [style*=line-through]"):
            old.decompose()
        return soup

    def fetch_listings(self):
        pending, seen, results = [self.list_url], set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 20:
                raise ValueError("一覧が20ページを超えました。巡回範囲を確認してください")
            seen.add(url)
            soup = self.soup(url)
            if self.city == "南九州市":
                nodes = soup.select(".entry-list-box")
                if not nodes:
                    raise ValueError("南九州市の物件一覧を読めません")
                for node in nodes:
                    item = self.parse_minamikyushu(node, url)
                    if item:
                        results[item.uid] = item
                for a in soup.select("a[data-page]"):
                    page = a.get("data-page", "")
                    if page.isdigit() and int(page) > 1:
                        parts = urlsplit(self.list_url)
                        query = dict(parse_qsl(parts.query))
                        query["page"] = page
                        pending.append(urlunsplit(parts._replace(query=urlencode(query))))
            else:
                links = {}
                for a in soup.select("a[href]"):
                    title = text(a)
                    if ((self.city == "指宿市" and "物件番号" in title)
                            or (self.city == "枕崎市" and re.search(r"No\.\s*\d+", title))):
                        if "売却" in title or "売買" in title:
                            detail = urljoin(url, a["href"])
                            if urlsplit(detail).netloc != urlsplit(self.list_url).netloc:
                                raise ValueError("市外の詳細URLを検出しました")
                            links[detail] = title
                if not links:
                    raise ValueError(f"{self.city}の売買物件リンクを読めません")
                for detail, title in links.items():
                    item = self.parse_detail(self.soup(detail), detail, title)
                    if item:
                        results[item.uid] = item
                if self.city == "指宿市":
                    for a in soup.select("a[href]"):
                        target = urljoin(url, a["href"])
                        if (urlsplit(target).netloc == urlsplit(self.list_url).netloc
                                and re.fullmatch(r"/ijyu/akiya_bank/index_\d+\.html", urlsplit(target).path)):
                            pending.append(target)
        return list(results.values())

    def make(self, number, title, url, value, data, address, floor="", land="", layout="", toilet=""):
        if not number or not address:
            raise ValueError(f"物件番号または住所が欠落: {url}")
        address = re.sub(r"\s+", "", address)
        if self.city not in address:
            address = self.city + address
        return Listing(
            source=self.source_id, listing_id=number, title=title, url=url,
            price_yen=price(value), address=address,
            floor_area_sqm=parse_area_sqm(floor), land_area_sqm=parse_area_sqm(land),
            layout=layout, toilet=toilet,
            parking_slots=parse_parking_slots("駐車場 " + data.get("駐車場", "")),
            description=" / ".join(f"{k}: {v}" for k, v in data.items()), raw=data,
        )

    def parse_minamikyushu(self, node, url):
        tag = text(node.select_one(".type-tag"))
        if "売買" not in tag:
            return None
        a = node.select_one(".head-title a")
        match = re.search(r"No\.\s*(\d+(?:-\d+)?)", text(a))
        if not match:
            raise ValueError("南九州市の物件番号がありません")
        data = fields(node)
        value = data.get("価格", "")
        if "賃貸" in tag:
            sale = re.search(r"売買\s*[:：]\s*(.*?)(?:賃貸|$)", value)
            if not sale:
                raise ValueError("売買・賃貸併記価格を分離できません")
            value = sale.group(1)
        return self.make(match.group(1), text(a), urljoin(url, a["href"]), value,
                         data, data.get("所在地", ""), data.get("延床面積", ""),
                         data.get("敷地面積", ""), data.get("間取り", ""))

    def parse_detail(self, soup, url, title):
        data = fields(soup)
        if self.city == "指宿市":
            kind = next((v for k, v in data.items() if k.startswith("掲載種別")), "")
            if "売却" not in kind:
                if "賃貸" in kind:
                    return None
                raise ValueError("指宿市の掲載種別がありません")
            value = next((v for k, v in data.items() if k.startswith("価格")), "")
            # 市の表記は売却価格 / 月額賃料。右側は絶対に価格として使わない。
            value = value.split("/")[0].strip()
            area = data.get("土地面積(建物面積)", "")
            areas = re.split(r"[()]", area)
            return self.make(data.get("物件番号", ""), title, url, value, data,
                             data.get("所在", ""), areas[1] if len(areas) > 1 else "",
                             areas[0], data.get("間取り", ""), data.get("トイレ", ""))
        kind = data.get("賃貸・売却の別", "")
        if "売買" not in kind and "売却" not in kind:
            if "賃貸" in kind:
                return None
            raise ValueError("枕崎市の掲載種別がありません")
        return self.make(data.get("登録番号", ""), title, url, data.get("希望価格", ""),
                         data, data.get("物件所在地", ""), data.get("建物", ""),
                         data.get("土地", ""), data.get("間取り", ""), data.get("設備状況", ""))
