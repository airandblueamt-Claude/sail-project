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

def notify_registration(user_name, user_email):
    """Notify admin of new registration + welcome the user."""
    # Admin notification
    send_email(ADMIN_EMAIL, f"New Registration: {user_name}",
        _base_html(f"""
            <h2 style="margin-top:0;">New User Registered</h2>
            <p><strong>{user_name}</strong> ({user_email}) has registered on SAIL.</p>
            <p>You can manage their role in <a href="{APP_URL}/employees/">Employee Management</a>.</p>
        """))

    # Welcome email to user
    send_email(user_email, "Welcome to SAIL",
        _base_html(f"""
            <h2 style="margin-top:0;">Welcome, {user_name}!</h2>
            <p>Your SAIL account has been created. You can now:</p>
            <ul>
                <li>Browse and book equipment</li>
                <li>Submit maintenance or support tickets</li>
                <li>Track your bookings and requests</li>
            </ul>
            <p><a href="{APP_URL}" style="display:inline-block;background:#4f6ef7;color:#fff;
               padding:10px 24px;border-radius:4px;text-decoration:none;">Open SAIL</a></p>
        """))


def notify_booking_submitted(booking, asset, requester):
    """Notify admin of new booking request."""
    send_email(ADMIN_EMAIL, f"Booking Request: {asset['asset_tag']}",
        _base_html(f"""
            <h2 style="margin-top:0;">New Booking Request</h2>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr><td style="padding:6px 0;color:#8a8fa8;">Requested by</td>
                    <td style="padding:6px 0;"><strong>{requester['name']}</strong> ({requester.get('email','')})</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Asset</td>
                    <td style="padding:6px 0;"><strong>{asset['asset_tag']}</strong> — {asset['eq_name']} ({asset['brand']})</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Dates</td>
                    <td style="padding:6px 0;">{booking['booked_from']} to {booking['booked_to']}</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Purpose</td>
                    <td style="padding:6px 0;">{booking.get('purpose','—')}</td></tr>
            </table>
            <p style="margin-top:16px;">
                <a href="{APP_URL}/bookings/admin" style="display:inline-block;background:#22c55e;color:#fff;
                   padding:10px 24px;border-radius:4px;text-decoration:none;">Review Bookings</a>
            </p>
        """))


def notify_booking_status(booking, asset, requester, new_status, admin_name=None):
    """Notify the requester that their booking status changed."""
    status_labels = {
        'approved': ('Approved', '#22c55e', 'Your booking has been approved. Please collect the equipment.'),
        'rejected': ('Rejected', '#ef4444', 'Your booking request has been declined.'),
        'checked_out': ('Checked Out', '#4f6ef7', 'Equipment has been handed over to you.'),
        'returned': ('Returned', '#22c55e', 'Equipment has been returned. Thank you!'),
        'cancelled': ('Cancelled', '#8a8fa8', 'Your booking has been cancelled.'),
    }
    label, color, message = status_labels.get(new_status, (new_status, '#8a8fa8', ''))

    user_email = requester.get('email')
    if not user_email:
        return

    send_email(user_email, f"Booking {label}: {asset['asset_tag']}",
        _base_html(f"""
            <h2 style="margin-top:0;">Booking {label}</h2>
            <div style="background:{color}20;border-left:4px solid {color};padding:12px 16px;
                        border-radius:4px;margin-bottom:16px;">
                <strong style="color:{color};">{message}</strong>
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr><td style="padding:6px 0;color:#8a8fa8;">Asset</td>
                    <td style="padding:6px 0;"><strong>{asset['asset_tag']}</strong> — {asset['eq_name']} ({asset['brand']})</td></tr>
                <tr><td style="padding:6px 0;color:#8a8fa8;">Dates</td>
                    <td style="padding:6px 0;">{booking['booked_from']} to {booking['booked_to']}</td></tr>
                {"<tr><td style='padding:6px 0;color:#8a8fa8;'>Processed by</td><td style='padding:6px 0;'>" + admin_name + "</td></tr>" if admin_name else ""}
            </table>
            <p style="margin-top:16px;">
                <a href="{APP_URL}/bookings/mine" style="display:inline-block;background:#4f6ef7;color:#fff;
                   padding:10px 24px;border-radius:4px;text-decoration:none;">View My Bookings</a>
            </p>
        """))


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
