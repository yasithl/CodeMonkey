from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/db.sqlite3"
    UPLOAD_DIR: str = "./data/uploads"
    RECEIPTS_DIR: str = "./data/receipts"
    GST_RATE: float = 0.15
    DEFAULT_CURRENCY: str = "NZD"

    model_config = {"env_file": ".env"}


settings = Settings()
