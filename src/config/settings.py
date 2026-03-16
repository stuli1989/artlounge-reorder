"""
Application settings. Uses environment variables with local dev fallbacks.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Tally connection (only used by sync agent, not the web app)
TALLY_HOST = os.environ.get("TALLY_HOST", "localhost")
TALLY_PORT = int(os.environ.get("TALLY_PORT", "9000"))

# Database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://reorder_app:password@localhost:5432/artlounge_reorder"
)

# Email notifications (for sync failure alerts)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

# Auth / JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

# Financial year
FY_START = "20250401"  # Apr 1, 2025
FY_END = "20260331"    # Mar 31, 2026

from datetime import date
FY_START_DATE = date(int(FY_START[:4]), int(FY_START[4:6]), int(FY_START[6:8]))
FY_END_DATE = date(int(FY_END[:4]), int(FY_END[4:6]), int(FY_END[6:8]))

# Company name in Tally
COMPANY_NAME = "Platinum Painting Essentials & Trading Pvt. Ltd."
