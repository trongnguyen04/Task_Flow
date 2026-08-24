import os
import warnings
from datetime import timedelta

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()

_SECRET_KEY_DEFAULT = "dev-secret-key"
_secret_key = os.getenv("SECRET_KEY", _SECRET_KEY_DEFAULT)

if _secret_key == _SECRET_KEY_DEFAULT:
    warnings.warn(
        "SECRET_KEY is using the insecure default value. "
        "Set the SECRET_KEY environment variable before deploying.",
        stacklevel=1,
    )

_debug = os.getenv("FLASK_DEBUG", "1") == "1"
_database_url = os.getenv("DATABASE_URL")

if not _database_url:
    warnings.warn(
        "DATABASE_URL is not set. Using a local SQLite database for development. "
        "Set DATABASE_URL before running with MySQL or deploying.",
        stacklevel=1,
    )
    _database_url = "sqlite:///taskflow_dev.db"


class Config:
    SECRET_KEY = _secret_key
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not _debug
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
