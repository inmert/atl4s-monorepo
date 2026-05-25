"""HTTP Basic dependency for both HTTP and WebSocket routes.

Reuses ``BAG_WEB_USER`` / ``BAG_WEB_PASS`` so the existing credentials and
.env entries keep working. Fails fast on partial config; if both vars are
unset, auth is disabled (only safe behind a closed firewall). Browsers
cache Basic credentials per origin and resend them on WebSocket upgrades,
so the same realm gates both HTTP and WS routes.
"""

import base64
import os
import secrets
import sys

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

USER = os.environ.get('BAG_WEB_USER', '')
PASS = os.environ.get('BAG_WEB_PASS', '')

if bool(USER) != bool(PASS):
    print('FATAL: set BOTH BAG_WEB_USER and BAG_WEB_PASS, or neither.', file=sys.stderr)
    sys.exit(1)

ENABLED = bool(USER)
if not ENABLED:
    print('WARN: BAG_WEB_USER/BAG_WEB_PASS unset; running without authentication.',
          file=sys.stderr)

_basic = HTTPBasic(realm='atl4s-dashboard')


def _check(credentials: HTTPBasicCredentials = Depends(_basic)) -> str:
    user_ok = secrets.compare_digest(credentials.username, USER)
    pass_ok = secrets.compare_digest(credentials.password, PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid credentials',
            headers={'WWW-Authenticate': 'Basic realm="atl4s-dashboard"'},
        )
    return credentials.username


def _noop() -> str:
    return 'anonymous'


require = _check if ENABLED else _noop


def check_websocket(ws: WebSocket) -> bool:
    """Return True if the WebSocket upgrade carries valid Basic credentials."""
    if not ENABLED:
        return True
    header = ws.headers.get('authorization', '')
    if not header.lower().startswith('basic '):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode('utf-8', errors='replace')
    except Exception:
        return False
    user, _, pw = decoded.partition(':')
    return secrets.compare_digest(user, USER) and secrets.compare_digest(pw, PASS)
