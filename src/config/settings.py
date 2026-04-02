"""
Application settings. Uses environment variables with local dev fallbacks.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Unicommerce API
UC_TENANT = os.getenv("UC_TENANT", "ppetpl")
UC_BASE_URL = f"https://{UC_TENANT}.unicommerce.com"
UC_USERNAME = os.getenv("UC_USERNAME")
UC_PASSWORD = os.getenv("UC_PASSWORD")
UC_TOKEN_EXPIRY_BUFFER = 300  # refresh token 5 min before expiry
UC_FACILITIES_FALLBACK = os.getenv("UC_FACILITIES", "ppetpl,ALIBHIWANDI,PPETPLKALAGHODA").split(",")

# Database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://reorder_app:password@localhost:5432/artlounge_reorder_uc"
)

# Email notifications via Resend API
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

# Auth / JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

# Financial year — dynamically computed based on Indian FY (April–March)
from datetime import date

def _get_fy_dates() -> tuple[date, date]:
    """Calculate current Indian financial year dates."""
    today = date.today()
    if today.month >= 4:  # Apr–Dec: current year's FY
        return date(today.year, 4, 1), date(today.year + 1, 3, 31)
    else:  # Jan–Mar: previous year's FY
        return date(today.year - 1, 4, 1), date(today.year, 3, 31)

FY_START_DATE, FY_END_DATE = _get_fy_dates()
FY_START = FY_START_DATE.strftime("%Y%m%d")
FY_END = FY_END_DATE.strftime("%Y%m%d")

# Company
COMPANY_NAME = "Platinum Painting Essentials & Trading Pvt. Ltd."
