"""Container management for the console (logic layer).

Talks to the Docker daemon over the bind-mounted ``/var/run/docker.sock``. Lists
the ``atl4s-*`` stack, inspects a single container, streams live logs and
resource stats over WebSockets, and starts/stops/restarts containers.

Every operation is restricted to ``NAME_PREFIX`` so the console can only touch
its own stack, never unrelated host containers. All routes require a valid
session (HTTP via ``auth.require``; WS via ``auth.check_websocket``).

Note on the read-only socket mount: ``/var/run/docker.sock:ro`` makes the
socket *file* read-only but does not restrict the Docker API carried over it, so
start/stop/restart work without changing the compose mount.
"""

import asyncio
import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Optional

import docker
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import auth

log = logging.getLogger('console.containers')

NAME_PREFIX = os.environ.get('CONTAINERS_NAME_PREFIX', 'atl4s-')
LOG_TAIL_DEFAULT = 200
LOG_TAIL_MAX = 2000
ACTIONS = {'start', 'stop', 'restart'}

# Docker container state → console severity level (shared vocab with the UI).
_STATE_LEVEL = {
    'running': 'ok', 'restarting': 'warn', 'paused': 'warn', 'created': 'warn',
    'exited': 'err', 'dead': 'err', 'removing': 'warn',
}
_HEALTH_LEVEL = {'healthy': 'ok', 'starting': 'warn', 'unhealthy': 'err'}


def _uptime(status: str, started_at: Optional[str]) -> Optional[float]:
    if status != 'running' or not started_at:
        return None
    # Docker returns ISO8601 with nanosecond precision; fromisoformat (3.10)
    # only accepts microseconds, so truncate the fractional part to 6 digits.
    iso = re.sub(r'\.(\d{6})\d+', r'.\1', started_at).replace('Z', '+00:00')
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except ValueError:
        return None


def _summary(c) -> dict:
    attrs = c.attrs
    state = attrs.get('State', {}) or {}
    config = attrs.get('Config', {}) or {}
    labels = config.get('Labels') or {}
    status = state.get('Status', 'unknown')
    health = (state.get('Health') or {}).get('Status')
    started = state.get('StartedAt') or None

    level = _STATE_LEVEL.get(status, 'warn')
    if health is not None:
        level = _HEALTH_LEVEL.get(health, level)

    return {
        'name': c.name,
        'service': labels.get('com.docker.compose.service'),
        'state': status,
        'health': health,
        'level': level,
        'image': config.get('Image'),
        'started_at': started,
        'uptime_sec': _uptime(status, started),
        'restart_count': attrs.get('RestartCount', 0),
    }


def _ports(net: dict) -> list[str]:
    out: list[str] = []
    for cport, binds in (net.get('Ports') or {}).items():
        if binds:
            out.extend(f"{b.get('HostIp', '')}:{b.get('HostPort')}→{cport}" for b in binds)
        else:
            out.append(cport)
    return out


def _detail(c, image_env_keys: Optional[set] = None) -> dict:
    attrs = c.attrs
    state = attrs.get('State', {}) or {}
    config = attrs.get('Config', {}) or {}
    hostcfg = attrs.get('HostConfig', {}) or {}
    net = attrs.get('NetworkSettings', {}) or {}
    labels = config.get('Labels') or {}

    cmd = config.get('Cmd') or config.get('Entrypoint') or []
    # Env values are surfaced so the operator can view/edit them. They can
    # contain secrets, so the UI masks them by default; access is already gated
    # by the session + closed firewall. Each var is tagged with whether it comes
    # from the image (a baseline default) vs. the container/compose.
    image_keys = image_env_keys if image_env_keys is not None else set()
    env = []
    for entry in (config.get('Env') or []):
        key, _, value = entry.partition('=')
        env.append({'key': key, 'value': value, 'from_image': key in image_keys})
    env.sort(key=lambda e: e['key'])

    detail = _summary(c)
    detail.update({
        'id': c.id[:12],
        'created': attrs.get('Created'),
        'command': ' '.join(cmd) if cmd else None,
        'restart_policy': (hostcfg.get('RestartPolicy') or {}).get('Name') or None,
        'network_mode': hostcfg.get('NetworkMode'),
        'networks': sorted((net.get('Networks') or {}).keys()),
        'ports': _ports(net),
        'mounts': [
            {
                'source': m.get('Source') or m.get('Name'),
                'destination': m.get('Destination'),
                'mode': m.get('Mode'),
                'rw': m.get('RW'),
            }
            for m in (attrs.get('Mounts') or [])
        ],
        'env': env,
        'compose_project': labels.get('com.docker.compose.project'),
        'exit_code': state.get('ExitCode'),
        'state_error': state.get('Error') or None,
    })
    return detail


class DockerService:
    """Lazily-connected Docker client; reconnects on the next call after a
    failure so a daemon hiccup doesn't wedge the console permanently."""

    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None
        self._error: Optional[str] = None

    def client(self) -> Optional[docker.DockerClient]:
        if self._client is not None:
            return self._client
        try:
            client = docker.from_env()
            client.ping()  # surface an unreachable socket here, not mid-request
            self._client, self._error = client, None
            log.info('connected to docker daemon')
        except Exception as exc:
            self._client, self._error = None, str(exc)
            log.warning('docker unavailable: %s', exc)
        return self._client

    @property
    def error(self) -> Optional[str]:
        return self._error

    def require_client(self) -> docker.DockerClient:
        client = self.client()
        if client is None:
            raise HTTPException(503, detail=f'docker unavailable: {self._error or "not configured"}')
        return client

    def list_summaries(self) -> list[dict]:
        client = self.client()
        if client is None:
            return []
        try:
            containers = client.containers.list(all=True, filters={'name': NAME_PREFIX})
        except Exception:
            log.exception('docker list failed')
            return []
        return sorted((_summary(c) for c in containers), key=lambda s: s['name'])

    def get(self, name: str):
        """Resolve a container by exact name within the prefix, or raise."""
        if not name.startswith(NAME_PREFIX):
            raise HTTPException(404, detail='unknown container')
        client = self.require_client()
        try:
            return client.containers.get(name)
        except docker.errors.NotFound:
            raise HTTPException(404, detail='unknown container')
        except docker.errors.APIError as exc:
            raise HTTPException(502, detail=f'docker error: {exc.explanation or exc}')

    def image_env_keys(self, container) -> set:
        """Env var names baked into the container's image — used to flag which
        vars are image defaults (vs. compose/runtime) in the editor."""
        client = self.client()
        image = (container.attrs.get('Config') or {}).get('Image')
        if client is None or not image:
            return set()
        try:
            img = client.images.get(image)
            return {e.split('=', 1)[0] for e in ((img.attrs.get('Config') or {}).get('Env') or [])}
        except Exception:
            return set()

    def set_env(self, name: str, env: dict) -> dict:
        """Recreate the container with a new environment.

        Docker can't mutate a running container's env, so this rebuilds it from
        the inspected Config + HostConfig (preserving image, command, labels,
        mounts, network mode, restart policy, GPU device requests, …) with the
        edited env, keeping the same name and compose labels. A rename-based
        backup is restored if creation fails, so a bad edit can't leave the
        service container-less.

        This is a *runtime* override: the next ``docker compose up`` reconciles
        against .env / compose and resets it.
        """
        client = self.require_client()
        old = self.get(name)
        attrs = old.attrs
        config = attrs.get('Config', {}) or {}
        host_config = attrs.get('HostConfig', {}) or {}
        image = config.get('Image')
        if not image:
            raise HTTPException(409, detail='cannot recreate: container has no image reference')

        was_running = (attrs.get('State', {}) or {}).get('Status') == 'running'
        env_list = [f'{k}={v}' for k, v in env.items()]
        backup = f'{name}__pre_env_edit'

        # Preserve ALL compose labels (project / service / number / config-hash)
        # so the container still looks exactly like a compose-managed one — a
        # plain `docker compose up` then treats the service as up-to-date and
        # leaves this runtime override in place (dropping the config-hash instead
        # makes compose's recreate path hit a name conflict). To revert to the
        # .env values, force a recreate from compose.
        labels = dict(config.get('Labels') or {})

        # Clear any leftover backup from a prior failed attempt.
        try:
            client.containers.get(backup).remove(force=True)
        except docker.errors.NotFound:
            pass

        if was_running:
            try:
                old.stop(timeout=10)
            except docker.errors.APIError:
                pass
        old.rename(backup)

        try:
            created = client.api.create_container(
                image=image,
                name=name,
                command=config.get('Cmd'),
                entrypoint=config.get('Entrypoint'),
                environment=env_list,
                labels=labels,
                working_dir=config.get('WorkingDir') or None,
                user=config.get('User') or '',
                host_config=host_config,
            )
            if was_running:
                client.api.start(created['Id'])
        except Exception as exc:
            # Roll back: drop any partial new container, restore the backup.
            try:
                client.containers.get(name).remove(force=True)
            except docker.errors.NotFound:
                pass
            try:
                bak = client.containers.get(backup)
                bak.rename(name)
                if was_running:
                    bak.start()
            except docker.errors.APIError:
                log.exception('rollback failed for %s', name)
            raise HTTPException(502, detail=f'env update failed, rolled back: {exc}')

        try:
            client.containers.get(backup).remove(force=True)
        except docker.errors.NotFound:
            pass

        container = client.containers.get(name)
        container.reload()
        log.warning('container %s recreated with %d env vars (runtime override)', name, len(env_list))
        return _detail(container, self.image_env_keys(container))


service = DockerService()

router = APIRouter(prefix='/api/containers', tags=['containers'])
ws_router = APIRouter()


class EnvUpdate(BaseModel):
    env: dict[str, str]


@router.get('', dependencies=[Depends(auth.require)])
def list_containers() -> dict:
    service.require_client()
    return {'available': True, 'containers': service.list_summaries()}


@router.get('/{name}', dependencies=[Depends(auth.require)])
def get_container(name: str) -> dict:
    container = service.get(name)
    return _detail(container, service.image_env_keys(container))


@router.put('/{name}/env', dependencies=[Depends(auth.require)])
def update_env(name: str, body: EnvUpdate) -> dict:
    for key in body.env:
        if not key or '=' in key or key != key.strip():
            raise HTTPException(400, detail=f'invalid env key: {key!r}')
    return service.set_env(name, body.env)


@router.get('/{name}/logs', dependencies=[Depends(auth.require)])
def get_logs(name: str, tail: int = LOG_TAIL_DEFAULT) -> dict:
    container = service.get(name)
    tail = max(1, min(tail, LOG_TAIL_MAX))
    try:
        raw = container.logs(tail=tail, timestamps=True)
    except docker.errors.APIError as exc:
        raise HTTPException(502, detail=f'logs failed: {exc.explanation or exc}')
    return {'logs': raw.decode('utf-8', 'replace')}


@router.get('/{name}/logs/download', dependencies=[Depends(auth.require)])
def download_logs(name: str, tail: str = 'all') -> StreamingResponse:
    container = service.get(name)
    if tail == 'all':
        amount: object = 'all'
    else:
        try:
            amount = max(1, min(int(tail), 1_000_000))
        except ValueError:
            amount = LOG_TAIL_DEFAULT
    try:
        # Sync generator → StreamingResponse iterates it in a threadpool, so the
        # event loop isn't blocked while a large log is streamed to the browser.
        stream = container.logs(stream=True, follow=False, tail=amount, timestamps=True)
    except docker.errors.APIError as exc:
        raise HTTPException(502, detail=f'logs failed: {exc.explanation or exc}')
    return StreamingResponse(
        stream,
        media_type='text/plain; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{name}.log"'},
    )


@router.post('/{name}/{action}', dependencies=[Depends(auth.require)])
def container_action(name: str, action: str) -> dict:
    if action not in ACTIONS:
        raise HTTPException(400, detail=f'unsupported action: {action}')
    container = service.get(name)
    try:
        getattr(container, action)()
    except docker.errors.APIError as exc:
        raise HTTPException(502, detail=f'{action} failed: {exc.explanation or exc}')
    container.reload()
    log.info('container %s %s by session', name, action)
    return _summary(container)


# --- Live streams (WebSocket) -----------------------------------------------

def _safe_put(queue: asyncio.Queue, item) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        pass  # drop under back-pressure; this is a live tail, not a transcript


def _cpu_percent(stat: dict) -> float:
    cpu, pre = stat.get('cpu_stats', {}), stat.get('precpu_stats', {})
    try:
        cpu_delta = cpu['cpu_usage']['total_usage'] - pre['cpu_usage']['total_usage']
        sys_delta = cpu['system_cpu_usage'] - pre['system_cpu_usage']
    except (KeyError, TypeError):
        return 0.0
    if cpu_delta <= 0 or sys_delta <= 0:
        return 0.0
    cpus = cpu.get('online_cpus') or len(cpu['cpu_usage'].get('percpu_usage') or []) or 1
    return round((cpu_delta / sys_delta) * cpus * 100.0, 1)


def _stats_frame(stat: dict) -> dict:
    mem = stat.get('memory_stats', {}) or {}
    usage = mem.get('usage', 0) or 0
    # Exclude page cache so the number matches `docker stats`.
    usage -= (mem.get('stats', {}) or {}).get('inactive_file', 0)
    limit = mem.get('limit', 0) or 0
    return {
        'cpu_percent': _cpu_percent(stat),
        'mem_bytes': max(usage, 0),
        'mem_limit': limit,
        'mem_percent': round(usage / limit * 100.0, 1) if limit else 0.0,
    }


async def _accept_for(ws: WebSocket, name: str):
    """Shared WS preamble: auth + resolve container, or close with a code."""
    if not auth.check_websocket(ws):
        await ws.close(code=4401)
        return None
    try:
        container = service.get(name)
    except HTTPException as exc:
        await ws.close(code=4404 if exc.status_code == 404 else 4400)
        return None
    await ws.accept()
    return container


@ws_router.websocket('/ws/containers/{name}/logs')
async def ws_logs(ws: WebSocket, name: str) -> None:
    container = await _accept_for(ws, name)
    if container is None:
        return

    try:
        tail = max(1, min(int(ws.query_params.get('tail', LOG_TAIL_DEFAULT)), LOG_TAIL_MAX))
    except ValueError:
        tail = LOG_TAIL_DEFAULT

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    stop = threading.Event()
    sentinel = object()
    stream = container.logs(stream=True, follow=True, tail=tail, timestamps=True)

    def pump() -> None:
        try:
            for chunk in stream:
                if stop.is_set():
                    break
                loop.call_soon_threadsafe(_safe_put, queue, chunk.decode('utf-8', 'replace'))
        except Exception:
            pass
        finally:
            loop.call_soon_threadsafe(_safe_put, queue, sentinel)

    threading.Thread(target=pump, daemon=True).start()
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            await ws.send_text(item)
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        try:
            stream.close()  # CancellableStream — unblocks the pump thread
        except Exception:
            pass


@ws_router.websocket('/ws/containers/{name}/stats')
async def ws_stats(ws: WebSocket, name: str) -> None:
    container = await _accept_for(ws, name)
    if container is None:
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=8)
    stop = threading.Event()
    sentinel = object()
    stream = container.stats(stream=True, decode=True)

    def pump() -> None:
        try:
            for stat in stream:
                if stop.is_set():
                    break
                loop.call_soon_threadsafe(_safe_put, queue, _stats_frame(stat))
        except Exception:
            pass
        finally:
            loop.call_soon_threadsafe(_safe_put, queue, sentinel)

    threading.Thread(target=pump, daemon=True).start()
    try:
        while True:
            item = await queue.get()
            if item is sentinel:
                break
            await ws.send_json(item)
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        try:
            stream.close()
        except Exception:
            pass
