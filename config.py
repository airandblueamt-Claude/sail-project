"""SAIL configuration."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sail.db")
SECRET_KEY = "sail-2026-secret-key"
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
PAGE_SIZE = 50

# ── Email (Gmail SMTP) ──────────────────────────────────────────────
ADMIN_EMAIL = "airandblueamt@gmail.com"
SMTP_EMAIL = "airandblueamt@gmail.com"
SMTP_PASSWORD = os.environ.get("SAIL_SMTP_PASSWORD", "YOUR_APP_PASSWORD_HERE")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
APP_URL = "http://localhost:5555"
