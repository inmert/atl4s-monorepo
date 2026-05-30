"""ATL4S Console — new operator dashboard (logic layer).

Runs as a second uvicorn inside the dashboard container on ``CONSOLE_PORT``
(default 8090), beside the legacy dashboard on 8089. Features from the legacy
dashboard are integrated here one at a time; today it owns the login flow and
serves the SPA. The design layer (the React app under ``console/ui/``) talks to
this process only over the HTTP/JSON endpoints below.
"""

import logging

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, containers, deployments
from .config import STATIC_DIR

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('console.main')

app = FastAPI(title='ATL4S Console')

app.include_router(containers.router)
app.include_router(containers.ws_router)
app.include_router(deployments.router)


class LoginBody(BaseModel):
    username: str
    password: str


def _auth_state(user: str | None) -> dict:
    return {'authenticated': user is not None, 'username': user, 'auth_required': auth.ENABLED}


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok'}


@app.get('/api/auth/me')
def me(request: Request) -> dict:
    return _auth_state(auth.current_user(request))


@app.post('/api/auth/login')
def login(body: LoginBody, response: Response) -> dict:
    if not auth.ENABLED:
        return _auth_state('anonymous')
    if not auth.credentials_valid(body.username, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Invalid username or password')
    auth.issue_session(response, body.username)
    return _auth_state(body.username)


@app.post('/api/auth/logout')
def logout(response: Response) -> dict:
    auth.clear_session(response)
    return _auth_state(None)


# --- SPA (design layer) ------------------------------------------------------
# The login screen lives inside the SPA, so the static bundle itself is served
# unauthenticated; data endpoints (added per-feature later) gate on
# ``auth.require``. Declared API routes above take precedence over this
# catch-all by registration order.

if (STATIC_DIR / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=str(STATIC_DIR / 'assets')), name='assets')


@app.get('/{path:path}')
def spa(path: str) -> FileResponse:
    target = STATIC_DIR / path
    if target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(STATIC_DIR / 'index.html'))
