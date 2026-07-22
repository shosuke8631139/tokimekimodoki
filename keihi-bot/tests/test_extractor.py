from app.extractor import parse_receipt_json


def test_parse_normal_receipt():
    raw = (
        '{"date": "2026-07-21", "amount": 1980, "vendor": "セブンイレブン",'
        ' "category": "消耗品費", "tax_rate": 10, "confidence": 0.92, "notes": null}'
    )
    r = parse_receipt_json(raw)
    assert r.is_receipt()
    assert r.amount == 1980
    assert r.date == "2026-07-21"
    assert "1,980円" in "\n".join(r.summary_lines())


def test_parse_non_receipt_image():
    raw = (
        '{"date": null, "amount": null, "vendor": null, "category": null,'
        ' "tax_rate": null, "confidence": 0, "notes": "領収書ではない"}'
    )
    r = parse_receipt_json(raw)
    assert not r.is_receipt()
    assert r.notes == "領収書ではない"


def test_confidence_is_clamped():
    raw = (
        '{"date": null, "amount": 100, "vendor": null, "category": null,'
        ' "tax_rate": null, "confidence": 1.7, "notes": null}'
    )
    assert parse_receipt_json(raw).confidence == 1.0
