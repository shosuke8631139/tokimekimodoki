"""領収書の抽出結果モデル。"""

from typing import Optional

from pydantic import BaseModel, Field


class Receipt(BaseModel):
    date: Optional[str] = Field(None, description="YYYY-MM-DD。読めなければ null")
    amount: Optional[int] = Field(None, description="税込合計(円)")
    vendor: Optional[str] = Field(None, description="店名・支払先")
    category: Optional[str] = Field(
        None, description="勘定科目の候補(会議費/旅費交通費/消耗品費など)"
    )
    tax_rate: Optional[int] = Field(None, description="8 または 10")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    notes: Optional[str] = Field(None, description="読み取りに不安がある箇所")

    def is_receipt(self) -> bool:
        """領収書として最低限の情報が取れているか。"""
        return self.amount is not None and self.amount > 0

    def summary_lines(self) -> list[str]:
        return [
            f"日付: {self.date or '(不明)'}",
            f"金額: {f'{self.amount:,}円' if self.amount is not None else '(不明)'}",
            f"支払先: {self.vendor or '(不明)'}",
            f"科目: {self.category or '(不明)'}",
            f"税率: {f'{self.tax_rate}%' if self.tax_rate is not None else '(不明)'}",
        ]
