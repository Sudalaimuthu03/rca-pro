import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    DB_HOST     = os.getenv("DB_HOST", "localhost")
    DB_PORT     = os.getenv("DB_PORT", "5432")
    DB_NAME     = os.getenv("DB_NAME", "rcai_db")
    DB_USER     = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")

    DATABASE_URL = os.getenv("DATABASE_URL") or (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "rcai-dev-secret-key")
    DEBUG      = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Sessions / auth cookie
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE   = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

    REMEMBER_COOKIE_DURATION = timedelta(
        days=int(os.getenv("REMEMBER_COOKIE_DURATION_DAYS", "14"))
    )

    HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
    HF_MODEL     = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    HF_API_URL   = os.getenv("HF_API_URL", "https://router.huggingface.co/v1/chat/completions")
    HF_TIMEOUT_SECONDS = int(os.getenv("HF_TIMEOUT_SECONDS", "45"))

    
    _cors_env = os.getenv("CORS_ORIGINS", "")
    CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["*"]
    
