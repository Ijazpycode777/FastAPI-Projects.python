from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    database_name: str
    database_user: str
    database_password: str
    database_host: str
    database_port: int

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"))

settings = Settings()