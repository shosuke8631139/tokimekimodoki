"""マネーフォワードへの登録。

2モードある:
- CsvRegistrar: マネーフォワード ME には公開APIがないため、MEの
  「CSVインポート」形式で data/expenses.csv に追記する(デフォルト)。
- ApiRegistrar: マネーフォワード クラウド経費のAPI(OAuth2)で経費明細を登録する。
  エンドポイントのパスは契約プラン・APIバージョンにより異なるため、
  環境変数 MF_API_BASE / MF_TOKEN_URL で差し替えられるようにしてある。
  導入時は公式ドキュメント(https://expense.moneyforward.com/api/index.html)で要確認。
"""

import csv
from pathlib import Path
from typing import Protocol

import httpx

from .config import Settings
from .models import Receipt

# マネーフォワード ME のCSVインポートで受け付けられる列構成
CSV_HEADER = ["計算対象", "日付", "内容", "金額(円)", "保有金融機関", "大項目", "中項目", "メモ"]


class Registrar(Protocol):
    def register(self, receipt: Receipt) -> str:
        """登録を実行し、ユーザーに見せる結果メッセージを返す。"""
        ...


class CsvRegistrar:
    def __init__(self, data_dir: Path, csv_name: str = "expenses.csv"):
        data_dir.mkdir(parents=True, exist_ok=True)
        self._csv_path = data_dir / csv_name

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    def register(self, receipt: Receipt) -> str:
        is_new = not self._csv_path.exists()
        with self._csv_path.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(CSV_HEADER)
            writer.writerow(
                [
                    "1",
                    (receipt.date or "").replace("-", "/"),
                    receipt.vendor or "不明",
                    # MEでは支出をマイナス金額で表す
                    -(receipt.amount or 0),
                    "LINE経費bot",
                    receipt.category or "未分類",
                    "",
                    receipt.notes or "",
                ]
            )
        return (
            "CSVに追記しました。マネーフォワード MEの「データ入出力 > CSVインポート」から"
            f"取り込んでください。\n({self._csv_path})"
        )


class ApiRegistrar:
    def __init__(self, settings: Settings, timeout: float = 30.0):
        self._s = settings
        self._timeout = timeout

    def _fetch_access_token(self) -> str:
        resp = httpx.post(
            self._s.mf_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._s.mf_refresh_token,
                "client_id": self._s.mf_client_id,
                "client_secret": self._s.mf_client_secret,
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def register(self, receipt: Receipt) -> str:
        token = self._fetch_access_token()
        url = f"{self._s.mf_api_base}/offices/{self._s.mf_office_id}/me/ex_transactions"
        payload = {
            "ex_transaction": {
                "recognized_at": receipt.date,
                "value": receipt.amount,
                "remark": receipt.vendor or "",
                "memo": receipt.notes or "",
            }
        }
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return "マネーフォワード クラウド経費に明細を登録しました。"


def build_registrar(settings: Settings) -> Registrar:
    if settings.register_mode == "api":
        return ApiRegistrar(settings)
    return CsvRegistrar(settings.data_dir)
