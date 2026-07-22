from app.models import Receipt
from app.moneyforward import CsvRegistrar
from app.store import Store


def make_receipt() -> Receipt:
    return Receipt(
        date="2026-07-21",
        amount=1980,
        vendor="テスト商店",
        category="消耗品費",
        tax_rate=10,
        confidence=0.9,
        notes=None,
    )


def test_idempotency(tmp_path):
    store = Store(tmp_path)
    assert store.mark_processed("msg-1")
    assert not store.mark_processed("msg-1")  # 二重処理はスキップ
    assert store.mark_processed("msg-2")


def test_pending_roundtrip(tmp_path):
    store = Store(tmp_path)
    token = store.save_pending(make_receipt())
    receipt = store.pop_pending(token)
    assert receipt is not None and receipt.amount == 1980
    assert store.pop_pending(token) is None  # 二度押しは無効


def test_csv_registrar(tmp_path):
    reg = CsvRegistrar(tmp_path)
    reg.register(make_receipt())
    content = reg.csv_path.read_text(encoding="utf-8-sig")
    lines = content.strip().splitlines()
    assert lines[0].startswith("計算対象,日付,内容")
    assert "2026/07/21" in lines[1]
    assert "-1980" in lines[1]  # MEでは支出はマイナス
    assert "テスト商店" in lines[1]
