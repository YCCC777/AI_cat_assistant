import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    全域配置設定，使用 pydantic-settings 從環境變數讀取並驗證。
    """
    # LINE API
    LINE_CHANNEL_SECRET: str
    LINE_CHANNEL_ACCESS_TOKEN: str

    # Gemini AI
    GEMINI_API_KEY: str
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash-lite"

    # Google Calendar
    GOOGLE_CALENDAR_ID: str
    # Google 憑證：優先從環境變數讀取 JSON 內容，否則從檔案讀取
    GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT: Optional[str] = None
    GOOGLE_SERVICE_ACCOUNT_JSON: str = "credentials/service_account.json"

    # Notion API
    NOTION_TOKEN: str
    NOTION_DATABASE_ID: str
    NOTION_USER_PROGRESS_DB_ID: Optional[str] = None
    NOTION_LEARNING_CARD_DB_ID: Optional[str] = None

    # 管理與安全
    ADMIN_LINE_USER_ID: str
    DAILY_TOKEN_LIMIT: int = 50000
    USER_DAILY_LIMIT: int = 8
    ADMIN_TRANSFER_PASSWORD: str = "admin"

    # 系統設定
    ENV: str = "production"
    # Hugging Face 預設使用 7860 端口
    PORT: int = 7860

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# 實例化配置
settings = Settings()
