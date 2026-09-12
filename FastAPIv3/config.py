from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    database_name: str
    database_user: str
    database_password: str
    database_host: str
    database_port: int

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / "db.env"))

settings = Settings()

class JWTSettings(BaseSettings):
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / "jwt.env"))

jwt_settings = JWTSettings()
