from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from akiya_watcher.scrapers.nansatsu_city import NansatsuCityScraper, price
from akiya_watcher.scrapers.minamisatsuma_bank import MinamisatsumaBankScraper
from akiya_watcher.main import collect


def table(data):
    return '<table>' + ''.join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in data.items()) + '</table>'


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def scraper(city):
    return NansatsuCityScraper({'id': 'test', 'city': city, 'list_url': 'https://example.test/list'})


def card(number, value, kind='売買'):
    return f'<div class="entry-list-box"><h3 class="head-title"><a href="/detail/{number}">No.{number} 家</a></h3><p class="type-tag">{kind}</p>' + table({'価格': value, '所在地': '南九州市', '間取り': '4K'}) + '</div>'


def test_sale_rent_split():
    obj = scraper('南九州市')
    item = obj.parse_minamikyushu(soup(card('130-2', '賃貸：4.5万円 売買：要相談', '賃貸,売買')), obj.list_url)
    assert item.price_yen is None
    assert item.listing_id == '130-2'
    assert obj.parse_minamikyushu(soup(card('1', '3万円', '賃貸')), obj.list_url) is None


def test_ibusuki_detail_not_old_title():
    obj = scraper('指宿市')
    html = table({'物件番号': '2602-10-02', '掲載種別(売却/賃貸)': '売却のみ(土地と建物)',
                  '価格(売却/1か月賃料)': '1,500,000円/30,000円', '所在': '指宿市',
                  '土地面積 (建物面積)': '395.04m2 (149.12m2)', '家財の有無': 'あり'})
    item = obj.parse_detail(soup(html), obj.list_url, '【売却/値下げ】家')
    assert item.price_yen == 1500000
    assert item.land_area_sqm == 395.04
    assert item.floor_area_sqm == 149.12
    assert item.advertised_previous_price_yen is None
    assert '家財の有無: あり' in item.description


def test_makurazaki_td_cells():
    obj = scraper('枕崎市')
    html = table({'登録番号': '１２４', '賃貸・売却の別': '売買', '希望価格': '80万円',
                  '物件所在地': '枕 崎市', '特記事項': '家財あり'}).replace('th>', 'td>')
    item = obj.parse_detail(soup(html), obj.list_url, 'No.124')
    assert item.price_yen == 800000
    assert item.listing_id == '124'
    assert item.address == '枕崎市'


def test_pagination_and_failure_atomic(monkeypatch):
    obj = scraper('南九州市')
    def get(url):
        if 'page=2' in url:
            return soup(card('2', '50万円'))
        return soup(card('1', '100万円') + '<a href="#" data-page="2">2</a>')
    monkeypatch.setattr(obj, 'soup', get)
    assert len(obj.fetch_listings()) == 2
    def broken(url):
        if 'page=2' in url:
            raise TimeoutError('test')
        return get(url)
    monkeypatch.setattr(obj, 'soup', broken)
    with pytest.raises(TimeoutError):
        obj.fetch_listings()


def test_minamisatsuma_partial_failure_not_delisted(tmp_path, monkeypatch):
    source = {'id': 'minamisatsuma_akiya_bank', 'type': 'minamisatsuma_bank',
              'list_urls': ['https://example.test/a', 'https://example.test/b']}
    cfg = {'db_path': str(tmp_path / 'test.db'), 'sources': [source]}
    def get(self, url):
        return SimpleNamespace(apparent_encoding='utf-8', text=table({
            '登録番号': '1' if url.endswith('/a') else '2', '所在地': '加世田', '価格': '●売却：100万円'}))
    monkeypatch.setattr(MinamisatsumaBankScraper, 'get', get)
    assert len(collect(cfg)[0]) == 2
    def broken(self, url):
        if url.endswith('/b'):
            raise TimeoutError('test')
        return get(self, url)
    monkeypatch.setattr(MinamisatsumaBankScraper, 'get', broken)
    items, gone, *_ = collect(cfg)
    assert len(items) == 1
    assert gone == []


@pytest.mark.parametrize('value,expected', [('0円', 0), ('無償譲渡', 0), ('要相談', None), ('80万円（応相談）', 800000)])
def test_price(value, expected):
    assert price(value) == expected


def test_ambiguous_price_fails():
    with pytest.raises(ValueError):
        price('200万円 100万円')


def test_price_drop_not_repeated_by_old_title(tmp_path):
    from akiya_watcher.storage import Store
    from akiya_watcher.criteria import Scorer
    from akiya_watcher.alerts import decide
    obj = scraper('枕崎市')
    store = Store(tmp_path / 'prices.db')
    def record(value):
        html = table({'登録番号': '124', '賃貸・売却の別': '売買', '希望価格': value,
                      '物件所在地': '枕崎市', '建物': '65㎡'})
        item = obj.parse_detail(soup(html), obj.list_url, '【値下げ】No.124')
        diff = store.upsert(item)
        return diff, decide(diff, Scorer({}).score(item, diff.context))
    first, _ = record('100万円')
    assert first.kind == 'new' and not first.context.price_changed
    diff, decision = record('80万円')
    assert diff.context.drop_pct == 20
    assert decision.notify and decision.kind == 'drop'
    diff, decision = record('80万円')
    assert not diff.context.price_changed and not decision.notify
    store.close()


def test_deleted_price_and_custom_source_id(monkeypatch):
    obj = MinamisatsumaBankScraper({'id': 'custom', 'list_urls': ['https://example.test']})
    html = table({'登録番号': '1', '価格': '●売却：<s>200万円</s>100万円'})
    monkeypatch.setattr(obj, 'get', lambda url: SimpleNamespace(text=html, apparent_encoding='utf-8'))
    item, = obj.fetch_listings()
    assert item.price_yen == 1000000 and item.source == 'custom'
    monkeypatch.setattr(obj, 'get', lambda url: SimpleNamespace(text='<html>maintenance</html>', apparent_encoding='utf-8'))
    with pytest.raises(ValueError):
        obj.fetch_listings()
    assert not obj.full_snapshot
