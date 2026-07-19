from pathlib import Path
from pydantic_settings import BaseSettings


_DUMMY_KEY_VALUES = {"", "dummy_replace_me", "your_api_key_here"}


class Settings(BaseSettings):
    app_name: str = "株価予測システム"
    version: str = "0.1.0"
    db_url: str = "sqlite:///./stock_prediction.db"
    model_version: str = "lgbm_v1"

    fred_api_key: str = ""
    jquants_api_key: str = ""
    # Phase2以降で使用予定 (現時点ではどのアダプタからも未参照だが、.envに設定済みのため
    # 起動時エラーを避けるためフィールドとして宣言しておく)
    edinet_api_key: str = ""
    estat_api_key: str = ""
    vantage_api_key: str = ""
    bea_api_key: str = ""
    bls_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"   # 未宣言の環境変数が.envに追加されても起動時エラーにしない

    def is_configured(self, key: str) -> bool:
        """APIキーが未設定/ダミー値でないかを判定する"""
        value = getattr(self, key, "") or ""
        return value.strip() not in _DUMMY_KEY_VALUES


settings = Settings()
