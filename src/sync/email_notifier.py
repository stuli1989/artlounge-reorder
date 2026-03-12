"""
Email notifications for sync status.
Uses SMTP (Gmail app password or any SMTP provider).
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL


def send_sync_notification(status: str, summary: dict, error_message: str = None):
    """
    Send email after sync completes or fails.

    Args:
        status: 'completed' or 'failed'
        summary: {categories_synced, items_synced, transactions_synced, new_parties_found}
        error_message: Error details if status='failed'
    """
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL]):
        print("  Email not configured, skipping notification")
        return

    subject = f"[Art Lounge Sync] {'Success' if status == 'completed' else 'FAILED'}"

    if status == "completed":
        body = f"""Nightly sync completed successfully.

Categories synced: {summary.get('categories_synced', 0)}
Items synced: {summary.get('items_synced', 0)}
Transactions synced: {summary.get('transactions_synced', 0)}
New parties found: {summary.get('new_parties_found', 0)}
"""
        if summary.get("new_parties_found", 0) > 0:
            body += "\nWARNING: New unclassified parties detected — classify them in the dashboard."
    else:
        body = f"""Nightly sync FAILED.

Error: {error_message}

Dashboard data may be stale. Check the sync agent on the AWS box.
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"  Notification email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  Failed to send email notification: {e}")
