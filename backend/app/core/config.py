"""
app/core/config.py — Centralised environment configuration
All environment variables are read here ONCE and imported everywhere else.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=False)

# ── App ───────────────────────────────────────────────────────────────────────
APP_NAME:    str   = os.environ.get("APP_NAME",    "IntrusionX SE")
APP_VERSION: str   = os.environ.get("APP_VERSION", "2.0.0")
DEBUG:       bool  = os.environ.get("DEBUG",        "True").lower() == "true"

# ── Server ────────────────────────────────────────────────────────────────────
API_HOST: str = os.environ.get("API_HOST", "127.0.0.1")
API_PORT: int = int(os.environ.get("API_PORT", "8000"))

# ── PostgreSQL ────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://osint_user:osint_pass@localhost:5432/intrusion_x_db",
)

# ── Firebase ──────────────────────────────────────────────────────────────────
FIREBASE_CRED_PATH:  str = os.environ.get("FIREBASE_CRED_PATH",  "/etc/secrets/firebase-service-account.json")
FIREBASE_PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "intrusion-x-se-default")

# ── Chatbot tokens ────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN:      str = os.environ.get("TELEGRAM_BOT_TOKEN",      "REPLACE_WITH_BOT_TOKEN")
WHATSAPP_VERIFY_TOKEN:   str = os.environ.get("WHATSAPP_VERIFY_TOKEN",   "REPLACE_WITH_VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN:   str = os.environ.get("WHATSAPP_ACCESS_TOKEN",   "REPLACE_WITH_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID:str = os.environ.get("WHATSAPP_PHONE_NUMBER_ID","REPLACE_WITH_PHONE_ID")

# ── LeakOSINT ─────────────────────────────────────────────────────────────────
LEAKOSINT_TOKEN:   str = os.environ.get("LEAKOSINT_TOKEN",   "1900800372:36uned3K")
LEAKOSINT_API_URL: str = os.environ.get("LEAKOSINT_API_URL", "https://leakosintapi.com/")
LEAKOSINT_LANG:    str = os.environ.get("LEAKOSINT_LANG",    "en")
LEAKOSINT_LIMIT:   int = int(os.environ.get("LEAKOSINT_LIMIT", "100"))

# ── HTTP / CORS / misc ────────────────────────────────────────────────────────
HTTP_TIMEOUT:       float = float(os.environ.get("HTTP_TIMEOUT", "12.0"))
USER_AGENT:         str   = os.environ.get("USER_AGENT", f"{APP_NAME}/{APP_VERSION} (OSINT Engine)")
CORS_ORIGINS:       str   = os.environ.get(
    "CORS_ORIGINS",
    "https://nexusscope.vercel.app,https://nexusscope.gaurangjadoun.in,http://localhost:5173,https://nexusscope.onrender.com",
)
PLAYWRIGHT_HEADLESS: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "True").lower() == "true"
