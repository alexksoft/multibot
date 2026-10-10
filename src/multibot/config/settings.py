from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kiro Gateway
    kiro_gateway_url: str = ""
    kiro_gateway_api_key: str = ""
    kiro_gateway_model: str = "claude-opus-4.7"

    # Google Sheets
    google_creds_path: str = "config/google-service-account.json"
    google_sheet_id: str = ""

    # Dialog logging
    dialog_log_enabled: bool = True
    dialog_log_sheet_id: str = ""

    # General
    bots_dir: str = "bots"
    db_path: str = "multibot.db"
    log_level: str = "INFO"
    admin_chat_id: str = ""

    # Admin panel
    admin_enabled: bool = False
    admin_host: str = "127.0.0.1"
    admin_port: int = 8600
    admin_username: str = "admin"
    admin_password_hash: str = ""
    admin_session_secret: str = "change_this_to_a_long_random_string"

    @property
    def dialog_log_sheet(self) -> str:
        return self.dialog_log_sheet_id or self.google_sheet_id


settings = Settings()
