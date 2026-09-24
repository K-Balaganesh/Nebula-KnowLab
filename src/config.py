"""Configuration management for Supermarket Ops Agent."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "generated_artifacts"
INVOICES_DIR = ARTIFACTS_DIR / "invoices"
DECKS_DIR = ARTIFACTS_DIR / "decks"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
INVOICES_DIR.mkdir(parents=True, exist_ok=True)
DECKS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "supermarket.db"))

# API Keys & Tokens
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Store Defaults
STORE_NAME = os.getenv("STORE_NAME", "Bala Supermarket").strip()
STORE_GSTIN = os.getenv("STORE_GSTIN", "29ABCDE1234F1Z5").strip()
STORE_PHONE = os.getenv("STORE_PHONE", "+91 9042678196").strip()
STORE_ADDRESS = os.getenv(
    "STORE_ADDRESS",
    "Shop 4, 12th Main, HAL 2nd Stage,Tenkasi,Tamil Nadu-627806"
).strip()
STORE_STATE = os.getenv("STORE_STATE", "TENKASI").strip()
STORE_STATE_CODE = os.getenv("STORE_STATE_CODE", "18").strip()
DEFAULT_PAYMENT_MODE = "UPI"
