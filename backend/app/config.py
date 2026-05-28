# app/config.py
from pydantic_settings import BaseSettings  # or 'from pydantic import BaseSettings' in older versions

class Settings(BaseSettings):
    DATABASE_URL: str
    # Your other config fields...

    class Config:
        env_file = ".env"

# !!! MAKE SURE THIS LINE EXISTS !!!
settings = Settings()