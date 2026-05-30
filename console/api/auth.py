"""Session auth for the console (logic layer).

Reuses ``BAG_WEB_USER`` / ``BAG_WEB_PASS`` — the same credentials as the legacy
dashboard's HTTP Basic — but presents a real login form instead of the browser
dialog:

- ``POST /api/auth/login`` validates the credentials and sets a signed,
  httpOnly session cookie.
- ``GET  /api/auth/me`` reports the current user (or that none is signed in).
- ``POST /api/auth/logout`` clears the cookie.

The session cookie carries an HMAC-signed ``username|issued_at`` token. The
signing secret is derived from the credentials by default, so sessions survive
a container restart with zero extra configuration; override with
``CONSOLE_SESSION_SECRET`` if you want to rotate or share it explicitly.

If both credential vars are unset, auth is disabled (every request is treated
as ``anonymous``) — only safe behind a closed firewall, mirroring the legacy
dashboard's behaviour.
"""

import base64
import hashlib
import hmac
import os
import secrets
import sys
import time

from fastapi import HTTPException, Request, Response, status

USER = os.environ.get('BAG_WEB_USER', '')
PASS = os.environ.get('BAG_WEB_PASS', '')

if bool(USER) != bool(PASS):
    print('FATAL: set BOTH BAG_WEB_USER and BAG_WEB_PASS, or neither.', file=sys.stderr)
    sys.exit(1)

ENABLED = bool(USER)
if not ENABLED:
    print('WARN: BAG_WEB_USER/BAG_WEB_PASS unset; console running without authentication.',
          file=sys.stderr)

COOKIE_NAME = 'atl4s_console_session'
SESSION_TTL = int(os.environ.get('CONSOLE_SESSION_TTL', str(7 * 24 * 3600)))

# Stable secret derived from the credentials so sessions survive a restart with
# zero extra config. Set CONSOLE_SESSION_SECRET to override.
_SECRET = (os.environ.get('CONSOLE_SESSION_SECRET')
           or hashlib.sha256(f'atl4s-console:{USER}:{PASS}'.encode()).hexdigest()).encode()


def _sign(payload_b64: str) -> str:
    mac = hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()
    return f'{payload_b64}.{mac}'


def _make_token(username: str) -> str:
    payload = f'{username}|{int(time.time())}'.encode()
    return _sign(base64.urlsafe_b64encode(payload).decode())


def _verify(token: str) -> str | None:
    payload_b64, _, mac = token.rpartition('.')
    if not payload_b64 or not mac:
        return None
    expected = hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        username, _, issued = base64.urlsafe_b64decode(payload_b64).decode().partition('|')
        if int(time.time()) - int(issued) > SESSION_TTL:
            return None
        return username
    except (ValueError, UnicodeDecodeError):
        return None


def credentials_valid(username: str, password: str) -> bool:
    return (secrets.compare_digest(username, USER)
            and secrets.compare_digest(password, PASS))


def issue_session(response: Response, username: str) -> None:
    response.set_cookie(
        COOKIE_NAME, _make_token(username),
        max_age=SESSION_TTL, httponly=True, samesite='lax', path='/')


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path='/')


def current_user(request: Request) -> str | None:
    """Return the signed-in username, or None. ``anonymous`` when auth is off."""
    if not ENABLED:
        return 'anonymous'
    token = request.cookies.get(COOKIE_NAME)
    return _verify(token) if token else None


def require(request: Request) -> str:
    """FastAPI dependency: 401 unless a valid session is present."""
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='authentication required')
    return user


def check_websocket(ws) -> bool:
    """True if the WebSocket upgrade carries a valid session cookie.

    Browsers attach same-origin cookies to the upgrade request, so the session
    established over HTTP gates the WS streams too (live logs / stats).
    """
    if not ENABLED:
        return True
    token = ws.cookies.get(COOKIE_NAME)
    return bool(token) and _verify(token) is not None
