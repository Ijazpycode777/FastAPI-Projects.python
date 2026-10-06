from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")  
settings=Settings()

class JWTSettings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    model_config = SettingsConfigDict(env_file=["jwt.env"],extra="ignore")
jwt_settings = JWTSettings()