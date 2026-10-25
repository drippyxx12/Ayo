"""Encrypted transactional-email outbox; delivery requires explicit configuration."""
import json
import os
import time
from urllib.parse import urlencode

import httpx
from sqlalchemy import select, update

from ayo.models import MailOutbox


def queue_identity_mail(session, fernet, user, purpose, token, origin):
    session.execute(update(MailOutbox).where(MailOutbox.user_id == user.id,
        MailOutbox.kind == purpose, MailOutbox.status == 'pending').values(status='superseded'))
    path = '/verify-email' if purpose == 'verify_email' else '/reset-password'
    payload = {'url': origin + path + '?' + urlencode({'token': token}), 'purpose': purpose}
    session.add(MailOutbox(user_id=user.id, kind=purpose, recipient=user.email,
                          payload_cipher=fernet.encrypt(json.dumps(payload).encode()).decode(),
                          status='pending', created_at=time.time()))


def deliver_one(session, fernet):
    """Used by an operator-run worker. No secret or recipient is logged."""
    if os.getenv('AYO_MAIL_SEND_AUTHORIZED') != '1':
        raise RuntimeError('Transactional email delivery has not been authorized.')
    key, sender = os.getenv('RESEND_API_KEY'), os.getenv('MAIL_FROM')
    if not key or not sender:
        raise RuntimeError('Transactional email provider is not configured.')
    now = time.time()
    session.execute(update(MailOutbox).where(MailOutbox.status == 'pending',
        ((MailOutbox.kind == 'reset_password') & (MailOutbox.created_at <= now - 1800)) |
        ((MailOutbox.kind == 'verify_email') & (MailOutbox.created_at <= now - 86400))).values(status='expired'))
    row = session.scalar(select(MailOutbox).where(MailOutbox.status == 'pending')
                         .order_by(MailOutbox.id).with_for_update(skip_locked=True))
    if row is None:
        return False
    payload = json.loads(fernet.decrypt(row.payload_cipher.encode()))
    subject = 'Verify your Ayo email' if row.kind == 'verify_email' else 'Reset your Ayo password'
    # Idempotency prevents a worker crash/retry from duplicating this message.
    response = httpx.post('https://api.resend.com/emails', timeout=20,
        headers={'Authorization': 'Bearer ' + key, 'Idempotency-Key': f'ayo-account-{row.id}'},
        json={'from': sender, 'to': [row.recipient], 'subject': subject,
              'text': subject + '\n\n' + payload['url'] + '\n\nIf you did not request this, ignore this email.'})
    if response.status_code not in (200, 201):
        raise RuntimeError('Transactional email provider rejected delivery.')
    row.status = 'sent'
    return True
