"""SAIL configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB path is overridable via env so deploys can point it at a mounted volume.
DB_PATH = os.environ.get("SAIL_DB_PATH", os.path.join(BASE_DIR, "sail.db"))
SECRET_KEY = os.environ.get(
    "SAIL_SECRET_KEY",
    "dev-only-do-not-use-in-production-set-SAIL_SECRET_KEY",
)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
PAGE_SIZE = 50

# ── Email (Gmail SMTP) ──────────────────────────────────────────────
ADMIN_EMAIL = "airandblueamt@gmail.com"
SMTP_EMAIL = "airandblueamt@gmail.com"
SMTP_PASSWORD = os.environ.get("SAIL_SMTP_PASSWORD", "hzirfgqyfpcsscfw")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
APP_URL = os.environ.get("SAIL_APP_URL", "http://10.20.6.56")
