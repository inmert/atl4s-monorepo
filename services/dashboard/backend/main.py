"""FastAPI app for the ATL4S dashboard.

Serves the React/Vite frontend, exposes ``/healthz``, proxies bag-plane
operations to rosbag-manager under ``/api/*``, and bridges live ROS
topics + camera frames to WebSocket clients under ``/ws/*``.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import rclpy
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import auth, proxy
from backend.camera import camera
from backend.config import STATIC_DIR
from backend.containers import inspector as docker_inspector, router as containers_router
from backend.health import router as health_router
from backend.robots import camera_topics, registry, router as robots_router
from backend.ros import router as ros_router, sample_socket
from backend.topics import bridge, topics_from_registry

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('dashboard.main')


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    robots = registry.load()
    docker_inspector.connect()
    rclpy.init()
    bridge.set_loop(loop)
    bridge.set_extra_topics(topics_from_registry(robots))
    camera.set_loop(loop)
    camera.set_topics(list(camera_topics(robots).values()))
    bridge.start()
    camera.start()
    log.info('ROS bridges started')
    async with proxy.lifespan():
        try:
            yield
        finally:
            bridge.stop()
            camera.stop()
            rclpy.shutdown()


app = FastAPI(title='ATL4S dashboard', lifespan=lifespan)


@app.get('/healthz')
def healthz() -> dict:
    return {'status': 'ok'}


app.include_router(robots_router)
app.include_router(ros_router)
app.include_router(containers_router)
app.include_router(health_router)
app.include_router(proxy.router)


@app.websocket('/ws/topics')
async def ws_topics(ws: WebSocket) -> None:
    if not auth.check_websocket(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    bridge.add_subscriber(queue)
    try:
        for snapshot in bridge.snapshot():
            await ws.send_json(snapshot)
        while True:
            msg = await queue.get()
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        bridge.remove_subscriber(queue)


@app.websocket('/ws/ros/sample/{topic:path}')
async def ws_ros_sample(ws: WebSocket, topic: str) -> None:
    # FastAPI strips the leading slash from path parameters; restore it so
    # the topic name matches what's on the bus.
    if not topic.startswith('/'):
        topic = '/' + topic
    try:
        await sample_socket(ws, topic)
    except WebSocketDisconnect:
        pass


@app.websocket('/ws/camera/{robot_id}')
async def ws_camera(ws: WebSocket, robot_id: str) -> None:
    if not auth.check_websocket(ws):
        await ws.close(code=4401)
        return
    robot = registry.get(robot_id)
    if robot is None or 'camera' not in robot.telemetry:
        await ws.close(code=4404)
        return
    topic = robot.telemetry['camera']
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=4)
    camera.add_subscriber(topic, queue)
    try:
        latest = camera.latest(topic)
        if latest is not None:
            await ws.send_bytes(latest)
        while True:
            jpeg = await queue.get()
            await ws.send_bytes(jpeg)
    except WebSocketDisconnect:
        pass
    finally:
        camera.remove_subscriber(topic, queue)


if (STATIC_DIR / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=str(STATIC_DIR / 'assets')), name='assets')


@app.get('/{path:path}', dependencies=[Depends(auth.require)])
def spa_fallback(path: str) -> FileResponse:
    target = STATIC_DIR / path
    if target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(STATIC_DIR / 'index.html'))
