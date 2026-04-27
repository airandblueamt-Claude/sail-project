"""Email notifications for SAIL — uses Gmail SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_EMAIL, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT, ADMIN_EMAIL, APP_URL
import threading


def _send_async(msg):
    """Send email in background thread so it doesn't block the request."""
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


def send_email(to, subject, html_body):
    """Send an HTML email via Gmail SMTP (non-blocking)."""
    if not SMTP_PASSWORD or SMTP_PASSWORD == "YOUR_APP_PASSWORD_HERE":
        print(f"[EMAIL SKIP] No SMTP password configured. Would send to {to}: {subject}")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = f"SAIL System <{SMTP_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = f"SAIL - {subject}"
    msg.attach(MIMEText(html_body, "html"))

    thread = threading.Thread(target=_send_async, args=(msg,))
    thread.daemon = True
    thread.start()


def _base_html(content):
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                max-width:600px;margin:0 auto;padding:20px;">
        <div style="background:#2D3142;padding:16px 24px;border-radius:8px 8px 0 0;">
            <h1 style="color:#fff;font-size:18px;margin:0;">SAIL</h1>
            <p style="color:#8a8fa8;font-size:12px;margin:4px 0 0;">Smart Asset Inventory &amp; Logistics</p>
        </div>
        <div style="background:#ffffff;border:1px solid #e2e4ec;border-top:none;
                    padding:24px;border-radius:0 0 8px 8px;">
            {content}
        </div>
        <p style="font-size:11px;color:#8a8fa8;margin-top:12px;text-align:center;">
            This is an automated message from SAIL. <a href="{APP_URL}">Open SAIL</a>
        </p>
    </div>"""


# ── Notification functions ───────────────────────────────────────────

def notify_ticket_created(ticket, submitter):
    """Notify admin of new ticket."""
    priority_colors = {'low': '#22c55e', 'medium': '#f59e0b', 'high': '#f97316', 'critical': '#ef4444'}
    pcolor = priority_colors.get(ticket['priority'], '#8a8fa8')

    send_email(ADMIN_EMAIL, f"New Ticket {ticket['ticket_number']}: {ticket['title']}",
        _base_html(f"""
            <h2 style="margin-top:0;">New Ticket</h2>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr><td style="padding:6px 0;color:#8a8fa8;">Ticket</td>
                    <td style="padding:6px 0;"><strong>{ticket['ticket_number']}</strong></td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Type</td>
                    <td style="padding:6px 0;">{ticket['type']}</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Priority</td>
                    <td style="padding:6px 0;"><span style="color:{pcolor};font-weight:bold;">{ticket['priority'].upper()}</span></td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Submitted by</td>
                    <td style="padding:6px 0;">{submitter['name']} ({submitter.get('email','')})</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Title</td>
                    <td style="padding:6px 0;">{ticket['title']}</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Description</td>
                    <td style="padding:6px 0;">{ticket.get('description','—')}</td></tr>
            </table>
            <p style="margin-top:16px;">
                <a href="{APP_URL}/tickets/" style="display:inline-block;background:#4f6ef7;color:#fff;
                   padding:10px 24px;border-radius:4px;text-decoration:none;">View Tickets</a>
            </p>
        """))


def notify_ticket_update(ticket, user_email, update_type, updater_name=None):
    """Notify ticket submitter of status change or comment."""
    if not user_email:
        return

    if update_type == 'status_change':
        subject = f"Ticket {ticket['ticket_number']} — Status: {ticket['status']}"
        detail = f"Your ticket status has been updated to <strong>{ticket['status']}</strong>."
        if ticket.get('resolution'):
            detail += f"<br><br><strong>Resolution:</strong> {ticket['resolution']}"
    else:
        subject = f"New comment on {ticket['ticket_number']}"
        detail = "A new comment has been added to your ticket."

    send_email(user_email, subject,
        _base_html(f"""
            <h2 style="margin-top:0;">{subject}</h2>
            <p>{detail}</p>
            {"<p style='color:#8a8fa8;'>Updated by: " + updater_name + "</p>" if updater_name else ""}
            <p style="margin-top:16px;">
                <a href="{APP_URL}/tickets/{ticket['id']}" style="display:inline-block;background:#4f6ef7;color:#fff;
                   padding:10px 24px;border-radius:4px;text-decoration:none;">View Ticket</a>
            </p>
        """))
