"""Email notifications for SAIL — uses Gmail SMTP."""
import html
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import SMTP_EMAIL, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT, ADMIN_EMAIL, APP_URL
import threading


def _esc(value):
    """HTML-escape a value for safe interpolation into an email body."""
    return html.escape('' if value is None else str(value))


def _esc_multiline(value):
    """HTML-escape and convert newlines to <br> for multi-line bodies."""
    return _esc(value).replace('\n', '<br>')


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


def is_email_configured():
    """True if an SMTP app password is set, so sends will actually go out."""
    return bool(SMTP_PASSWORD) and SMTP_PASSWORD != "YOUR_APP_PASSWORD_HERE"


def send_email_with_attachment(recipients, subject, html_body,
                               attachment_name, attachment_bytes,
                               mimetype="application/octet-stream"):
    """Send one email with a single binary attachment (e.g. an .xlsx report).

    `recipients` may be a string or a list. Returns True if the send was
    dispatched, False if SMTP isn't configured (so the caller can warn).
    """
    from email.mime.application import MIMEApplication

    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False
    if not is_email_configured():
        print(f"[EMAIL SKIP] No SMTP password. Would send '{subject}' "
              f"to {recipients} with attachment {attachment_name}")
        return False

    msg = MIMEMultipart()
    msg["From"] = f"SAIL System <{SMTP_EMAIL}>"
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"SAIL - {subject}"
    msg.attach(MIMEText(html_body, "html"))

    subtype = mimetype.split("/", 1)[-1]
    part = MIMEApplication(attachment_bytes, _subtype=subtype)
    part.add_header("Content-Disposition", "attachment",
                    filename=attachment_name)
    msg.attach(part)

    thread = threading.Thread(target=_send_async, args=(msg,))
    thread.daemon = True
    thread.start()
    return True


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
    """Email the ticket creator confirming their submission, and copy admin."""
    priority_colors = {'low': '#22c55e', 'medium': '#f59e0b', 'high': '#f97316', 'critical': '#ef4444'}
    priority = ticket.get('priority', 'medium')
    pcolor = priority_colors.get(priority, '#8a8fa8')
    asset_label = f"{ticket.get('asset_tag') or ''} — {ticket.get('equipment_name') or ''}".strip(" —")

    ticket_number = _esc(ticket['ticket_number'])
    name = _esc(submitter.get('name', '')) if submitter else ''
    asset_html = _esc(asset_label) or '—'
    priority_html = _esc(priority.upper())
    title_html = _esc(ticket['title'])
    description_html = _esc_multiline(ticket.get('description') or '—')
    ticket_id = _esc(ticket.get('id', ''))

    body = _base_html(f"""
        <h2 style="margin-top:0;">Ticket {ticket_number} created</h2>
        <p>Hi {name},</p>
        <p>Your ticket has been recorded. The AMT team will follow up.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:6px 0;color:#8a8fa8;">Ticket</td>
                <td style="padding:6px 0;"><strong>{ticket_number}</strong></td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Asset</td>
                <td style="padding:6px 0;">{asset_html}</td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Priority</td>
                <td style="padding:6px 0;"><span style="color:{pcolor};font-weight:bold;">{priority_html}</span></td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Title</td>
                <td style="padding:6px 0;">{title_html}</td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Description</td>
                <td style="padding:6px 0;">{description_html}</td></tr>
        </table>
        <p style="margin-top:16px;">
            <a href="{APP_URL}/tickets/{ticket_id}" style="display:inline-block;background:#4f6ef7;color:#fff;
               padding:10px 24px;border-radius:4px;text-decoration:none;">View Ticket</a>
        </p>
    """)

    creator_email = submitter.get('email') if submitter else None
    if creator_email:
        send_email(creator_email, f"Ticket {ticket['ticket_number']} created: {ticket['title']}", body)
    if ADMIN_EMAIL and ADMIN_EMAIL != creator_email:
        send_email(ADMIN_EMAIL, f"New Ticket {ticket['ticket_number']}: {ticket['title']}", body)


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
    ticket_number = _esc(ticket['ticket_number'])
    title_html = _esc(ticket['title'])
    asset_html = _esc(asset_label)
    if kind == 'created':
        subject = f"Ticket #{ticket['ticket_number']} received: {ticket['title']}"
        body_html = f"""
        <p>Hi,</p>
        <p>We have received your issue and opened ticket
           <strong>#{ticket_number}</strong>.</p>
        <p><strong>Asset:</strong> {asset_html}<br>
           <strong>Issue:</strong> {title_html}</p>
        <p><strong>What you reported:</strong><br>
           {_esc_multiline(ticket.get('description') or '')}</p>
        <p>We will email you again once it is resolved. If you need to add
           anything, just reply to this email.</p>
        <p>— SAIL (AMT control team)</p>
        """
    elif kind == 'resolved':
        subject = f"Ticket #{ticket['ticket_number']} resolved: {ticket['title']}"
        body_html = f"""
        <p>Hi,</p>
        <p>Ticket <strong>#{ticket_number}</strong> has been
           resolved.</p>
        <p><strong>Asset:</strong> {asset_html}<br>
           <strong>Issue:</strong> {title_html}</p>
        <p><strong>Resolution:</strong><br>
           {_esc_multiline(ticket.get('resolution') or '')}</p>
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
    by_line = f"<p>Assigned by {_esc(assigner_name)}.</p>" if assigner_name else ""
    body_html = f"""
    <p>Hi,</p>
    <p>Ticket <strong>#{_esc(ticket['ticket_number'])}</strong> has been assigned
       to you.</p>
    <p><strong>Asset:</strong> {_esc(asset_label)}<br>
       <strong>Priority:</strong> {_esc(ticket.get('priority', 'medium').upper())}<br>
       <strong>Issue:</strong> {_esc(ticket['title'])}</p>
    <p><strong>Reported issue:</strong><br>
       {_esc_multiline(ticket.get('description') or '')}</p>
    {by_line}
    <p>Open the ticket in SAIL to update its status, add comments, or write
       the resolution when you are done.</p>
    """
    send_email(assignee_email, subject, _base_html(body_html))


def notify_booking_submitted(ticket, submitter, room_label, date, start_time,
                             end_time, attendees, purpose, asset_rows):
    """Confirmation email to the requester when a floor-plan booking lands.

    `submitter` must contain `email` and `name`. `asset_rows` is the list
    of asset dicts the requester picked (asset_tag + model_name).
    """
    email = submitter.get("email")
    if not email:
        return

    asset_block = ""
    if asset_rows:
        items = "".join(
            f"<li>{r['asset_tag']} — {r.get('model_name','')}</li>"
            for r in asset_rows
        )
        asset_block = f"<p><strong>Assets requested:</strong></p><ul>{items}</ul>"

    subject = (
        f"Booking request received — {ticket['ticket_number']} "
        f"({room_label} on {date})"
    )
    send_email(email, subject, _base_html(f"""
        <h2 style="margin-top:0;">Booking request received</h2>
        <p>Hi {submitter.get('name', 'there')},</p>
        <p>We have received your room-booking request and opened ticket
           <strong>#{ticket['ticket_number']}</strong>. The operations team
           will review and confirm shortly.</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;
                      margin-top:12px;">
            <tr><td style="padding:6px 0;color:#8a8fa8;width:120px;">Room</td>
                <td style="padding:6px 0;"><strong>{room_label}</strong></td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Date</td>
                <td style="padding:6px 0;">{date}</td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Time</td>
                <td style="padding:6px 0;">{start_time} – {end_time}</td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;">Attendees</td>
                <td style="padding:6px 0;">{attendees}</td></tr>
            <tr><td style="padding:6px 0;color:#8a8fa8;vertical-align:top;">Purpose</td>
                <td style="padding:6px 0;">{purpose}</td></tr>
        </table>
        {asset_block}
        <p style="margin-top:16px;">
            <a href="{APP_URL}/tickets/" style="display:inline-block;background:#4f6ef7;
               color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none;">
               View my tickets</a>
        </p>
        <p style="color:#8a8fa8;font-size:12px;margin-top:16px;">
            You will get another email once the booking is approved or closed.
        </p>
    """))


def notify_booking_approved(ticket, submitter, room_label, date,
                             start_time, end_time):
    """Tell the requester their booking has been approved by ops."""
    email = submitter.get("email")
    if not email:
        return
    subject = (
        f"Booking approved — {ticket['ticket_number']} "
        f"({room_label} on {date})"
    )
    send_email(email, subject, _base_html(f"""
        <h2 style="margin-top:0;">Your booking is approved</h2>
        <p>Hi {submitter.get('name', 'there')},</p>
        <p>Ticket <strong>#{ticket['ticket_number']}</strong> for
           <strong>{room_label}</strong> on {date}
           ({start_time} – {end_time}) has been approved by the operations
           team. The room is reserved for you for that window.</p>
        <p>When you are done, please leave the room as you found it. The
           operations team will close the booking and verify any equipment
           you used.</p>
        <p style="margin-top:16px;">
            <a href="{APP_URL}/tickets/" style="display:inline-block;background:#22c55e;
               color:#fff;padding:10px 24px;border-radius:4px;text-decoration:none;">
               View ticket</a>
        </p>
    """))


def notify_booking_closed(ticket, submitter, room_label, date, returns):
    """Tell the requester their booking has been closed and assets verified.

    `returns` is a list of dicts: {asset_tag, model_name, state, notes}.
    state ∈ {'returned_good', 'damaged', 'missing'}.
    Also CCs ADMIN_EMAIL when any return is damaged or missing.
    """
    email = submitter.get("email")
    if not email:
        return

    rows = "".join(
        f"<tr><td style='padding:4px 8px;'>{r['asset_tag']}</td>"
        f"<td style='padding:4px 8px;'>{r.get('model_name','')}</td>"
        f"<td style='padding:4px 8px;'>"
        f"<span style='color:{'#22c55e' if r['state']=='returned_good' else '#ef4444'};'>"
        f"{r['state'].replace('_',' ')}</span></td></tr>"
        for r in (returns or [])
    )
    return_table = (
        f"<table style='width:100%;border-collapse:collapse;font-size:14px;"
        f"border:1px solid #e2e4ec;margin-top:12px;'>"
        f"<thead><tr style='background:#f5f6fa;'>"
        f"<th style='padding:6px 8px;text-align:left;'>Asset</th>"
        f"<th style='padding:6px 8px;text-align:left;'>Model</th>"
        f"<th style='padding:6px 8px;text-align:left;'>Return state</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
        if rows else "<p>No assets were checked out for this booking.</p>"
    )

    has_issue = any(r.get('state') in ('damaged', 'missing') for r in (returns or []))
    issue_note = (
        "<p style='color:#ef4444;margin-top:12px;'><strong>Note:</strong> "
        "one or more assets were flagged as damaged or missing — admin "
        "has been copied for follow-up.</p>"
        if has_issue else ""
    )

    subject = f"Booking closed — {ticket['ticket_number']} ({room_label} on {date})"
    body = _base_html(f"""
        <h2 style="margin-top:0;">Booking closed</h2>
        <p>Hi {submitter.get('name', 'there')},</p>
        <p>Ticket <strong>#{ticket['ticket_number']}</strong> for
           <strong>{room_label}</strong> on {date} has been closed by the
           operations team. The asset return verification is below.</p>
        {return_table}
        {issue_note}
        <p style="color:#8a8fa8;font-size:12px;margin-top:16px;">
            If anything looks wrong, reply to this email.
        </p>
    """)
    send_email(email, subject, body)
    if has_issue:
        send_email(ADMIN_EMAIL, "[Follow-up] " + subject, body)


def notify_ticket_update(ticket, user_email, update_type, updater_name=None):
    """Notify ticket submitter of status change or comment."""
    if not user_email:
        return

    if update_type == 'status_change':
        subject = f"Ticket {ticket['ticket_number']} — Status: {ticket['status']}"
        detail = f"Your ticket status has been updated to <strong>{_esc(ticket['status'])}</strong>."
        if ticket.get('resolution'):
            detail += f"<br><br><strong>Resolution:</strong> {_esc(ticket['resolution'])}"
    else:
        subject = f"New comment on {ticket['ticket_number']}"
        detail = "A new comment has been added to your ticket."

    updater_line = (
        f"<p style='color:#8a8fa8;'>Updated by: {_esc(updater_name)}</p>"
        if updater_name else ""
    )
    send_email(user_email, subject,
        _base_html(f"""
            <h2 style="margin-top:0;">{_esc(subject)}</h2>
            <p>{detail}</p>
            {updater_line}
            <p style="margin-top:16px;">
                <a href="{APP_URL}/tickets/{_esc(ticket['id'])}" style="display:inline-block;background:#4f6ef7;color:#fff;
                   padding:10px 24px;border-radius:4px;text-decoration:none;">View Ticket</a>
            </p>
        """))
