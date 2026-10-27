"""Authenticated, password-confirmed session and password controls."""
import time

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update

from ayo.identity import IdentityError, IdentityService, password_hash, password_verify, token_hash, validate_password
from ayo.models import AuthSession, IdentityToken, MailOutbox, User


def active_sessions(session, user_id, current_token, clock=time.time):
    current = token_hash(current_token) if current_token else ''
    rows = session.scalars(select(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > clock()).order_by(AuthSession.expires_at.desc())).all()
    # Never expose stored token hashes to the browser, even as resource IDs.
    return [{'current': row.token_hash == current, 'expires_at': row.expires_at} for row in rows]


def confirm_password(session, user_id, supplied):
    user = IdentityService(session).lock_user(user_id)
    if not user or user.disabled_at is not None or not password_verify(supplied, user.password_hash):
        raise IdentityError('password_confirmation_failed', 'The current password could not be confirmed.', 403)
    return user


def revoke_other_sessions(session, user_id, current_token, password):
    confirm_password(session, user_id, password)
    current = token_hash(current_token)
    result = session.execute(update(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.token_hash != current,
        AuthSession.revoked_at.is_(None)).values(revoked_at=time.time()))
    IdentityService(session).audit('account.other_sessions_revoked', user_id=user_id,
        resource_type='user', resource_id=user_id, details={'count': result.rowcount})


def change_password(session, user_id, current_password, new_password):
    user = confirm_password(session, user_id, current_password)
    validate_password(new_password)
    if password_verify(new_password, user.password_hash):
        raise IdentityError('password_unchanged', 'Choose a new password.', 400)
    user.password_hash = password_hash(new_password)
    session.execute(update(IdentityToken).where(IdentityToken.user_id == user_id,
        IdentityToken.purpose == 'reset_password', IdentityToken.consumed_at.is_(None)).values(consumed_at=time.time()))
    session.execute(update(MailOutbox).where(MailOutbox.user_id == user_id,
        MailOutbox.kind == 'reset_password', MailOutbox.status == 'pending').values(status='superseded'))
    session.execute(update(AuthSession).where(AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None)).values(revoked_at=time.time()))
    service = IdentityService(session)
    grant = service.create_session(user_id)
    service.audit('account.password_changed', user_id=user_id, resource_type='user', resource_id=user_id)
    return grant


def install_routes(mod, context, guard, start_session):
    @mod.app.post('/security/sessions/revoke-others')
    def revoke_sessions(request: Request, password: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        user, _ = context(request, sess)
        guard(request, csrf, sess)
        IdentityService(sess)._attempt('security-confirmation', str(user.id), limit=10, window=3600)
        sess.commit()  # Failed confirmations also consume the persistent limit.
        revoke_other_sessions(sess, user.id, request.session.get('sid'), password)
        sess.commit()
        return RedirectResponse('/security?updated=sessions', 303)

    @mod.app.post('/security/password')
    def update_password(request: Request, current_password: str = Form(...), new_password: str = Form(...),
                        csrf: str = Form(...), sess=Depends(mod.db)):
        user, _ = context(request, sess)
        guard(request, csrf, sess)
        IdentityService(sess)._attempt('security-confirmation', str(user.id), limit=10, window=3600)
        sess.commit()
        grant = change_password(sess, user.id, current_password, new_password)
        sess.commit()
        selected_business = request.session.get('business_id')
        start_session(request, grant)
        if selected_business:
            request.session['business_id'] = selected_business
        return RedirectResponse('/security?updated=password', 303)
