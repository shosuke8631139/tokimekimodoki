"""環境変数からの設定読み込み。

実値は .env や実行環境の環境変数で渡す(.env.example 参照)。
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    # LINE Messaging API
    line_channel_secret: str = field(
        default_factory=lambda: os.environ.get("LINE_CHANNEL_SECRET", "")
    )
    line_channel_access_token: str = field(
        default_factory=lambda: os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    )

    # OpenAI
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    openai_model: str = field(
        default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4o")
    )

    # 登録先モード: "csv"(MF MEへ手動インポートするCSVを生成) or "api"(クラウド経費API)
    register_mode: str = field(
        default_factory=lambda: os.environ.get("REGISTER_MODE", "csv")
    )

    # マネーフォワード クラウド経費 API(register_mode=api のときのみ必要)
    mf_client_id: str = field(default_factory=lambda: os.environ.get("MF_CLIENT_ID", ""))
    mf_client_secret: str = field(
        default_factory=lambda: os.environ.get("MF_CLIENT_SECRET", "")
    )
    mf_refresh_token: str = field(
        default_factory=lambda: os.environ.get("MF_REFRESH_TOKEN", "")
    )
    mf_office_id: str = field(default_factory=lambda: os.environ.get("MF_OFFICE_ID", ""))
    # エンドポイントは公式ドキュメントで要確認のため差し替え可能にしておく
    mf_api_base: str = field(
        default_factory=lambda: os.environ.get(
            "MF_API_BASE", "https://expense.moneyforward.com/api/external/v1"
        )
    )
    mf_token_url: str = field(
        default_factory=lambda: os.environ.get(
            "MF_TOKEN_URL", "https://expense.moneyforward.com/oauth/token"
        )
    )

    # データ保存先(SQLite と CSV)
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("DATA_DIR", "data"))
    )

    # これ未満の confidence は返信に警告を付ける
    confidence_warn_threshold: float = 0.7


def load_settings() -> Settings:
    return Settings()
