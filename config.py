import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://finance_user:replace-me@localhost:3306/personal_finance?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    WTF_CSRF_TIME_LIMIT = 3600
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Colombo")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    MAIL_HOST = os.environ.get("MAIL_HOST", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") == "1"
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    PASSWORD_RESET_TOKEN_MAX_AGE = 1800
    ADMIN_ANALYTICS_MIN_GROUP_SIZE = 10
    COMMUNITY_ANALYTICS_MIN_GROUP_SIZE = 10
    COMMUNITY_ANALYTICS_CATEGORY_LIMIT = 6
    SESSION_PROTECTION = "strong"
