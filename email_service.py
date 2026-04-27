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


def notify_affected_user(ticket, kind):
    """Email the affected end user about ticket creation or resolution.

    `ticket` is a dict-like row that must include: ticket_number, title,
    description, resolution, asset_tag, equipment_name, affected_user_email.
    `kind` ∈ {'created', 'resolved'}. No-op if affected_user_email is blank.
    """
    email = ticket.get('affected_user_email')
    if not email:
        return

    asset_label = f"{ticket.get('asset_tag', '')} — {ticket.get('equipment_name', '')}".strip(" —")
    if kind == 'created':
        subject = f"Ticket #{ticket['ticket_number']} received: {ticket['title']}"
        body_html = f"""
        <p>Hi,</p>
        <p>We have received your issue and opened ticket
           <strong>#{ticket['ticket_number']}</strong>.</p>
        <p><strong>Asset:</strong> {asset_label}<br>
           <strong>Issue:</strong> {ticket['title']}</p>
        <p><strong>What you reported:</strong><br>
           {(ticket.get('description') or '').replace(chr(10), '<br>')}</p>
        <p>We will email you again once it is resolved. If you need to add
           anything, just reply to this email.</p>
        <p>— SAIL (AMT control team)</p>
        """
    elif kind == 'resolved':
        subject = f"Ticket #{ticket['ticket_number']} resolved: {ticket['title']}"
        body_html = f"""
        <p>Hi,</p>
        <p>Ticket <strong>#{ticket['ticket_number']}</strong> has been
           resolved.</p>
        <p><strong>Asset:</strong> {asset_label}<br>
           <strong>Issue:</strong> {ticket['title']}</p>
        <p><strong>Resolution:</strong><br>
           {(ticket.get('resolution') or '').replace(chr(10), '<br>')}</p>
        <p>If the issue is not actually fixed, reply to this email and we
           will reopen the ticket.</p>
        <p>— SAIL (AMT control team)</p>
        """
    else:
        return

    send_email(email, subject, _base_html(body_html))


def notify_ticket_assigned(ticket, assignee_email, assigner_name=None):
    """Email an operation-team member when a ticket is assigned to them.

    `ticket` must include: ticket_number, title, description, priority,
    asset_tag, equipment_name. No-op if assignee_email is blank.
    """
    if not assignee_email:
        return

    asset_label = f"{ticket.get('asset_tag', '')} — {ticket.get('equipment_name', '')}".strip(" —")
    subject = f"Ticket #{ticket['ticket_number']} assigned to you: {ticket['title']}"
    by_line = f"<p>Assigned by {assigner_name}.</p>" if assigner_name else ""
    body_html = f"""
    <p>Hi,</p>
    <p>Ticket <strong>#{ticket['ticket_number']}</strong> has been assigned
       to you.</p>
    <p><strong>Asset:</strong> {asset_label}<br>
       <strong>Priority:</strong> {ticket.get('priority', 'medium').upper()}<br>
       <strong>Issue:</strong> {ticket['title']}</p>
    <p><strong>Reported issue:</strong><br>
       {(ticket.get('description') or '').replace(chr(10), '<br>')}</p>
    {by_line}
    <p>Open the ticket in SAIL to update its status, add comments, or write
       the resolution when you are done.</p>
    """
    send_email(assignee_email, subject, _base_html(body_html))


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
