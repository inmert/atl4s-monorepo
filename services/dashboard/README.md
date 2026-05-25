# dashboard

Single human-facing surface for ATL4S. React + Vite + TS frontend, FastAPI + rclpy backend, served from one container. HTTP Basic on TCP 8089 (runs on 8090 during the staged build until bag-web is retired).

Owns no bag state — proxies every bag-plane action to `rosbag-manager` on `127.0.0.1:8086`. Owns no compute — perception services do inference; the dashboard renders, browses, and triggers. 3D visualisation is deferred to Foxglove Studio via a deep link; the in-app view is raw data + 2D map + camera.

## Surfaces

Scaffold ships placeholder pages only; features land per the [HANDOFF dashboard plan](../../HANDOFF.md).

| Path | Status |
|---|---|
| `GET /healthz` | live |
| `GET /` (and SPA fallback) | live — serves the built React app |
| `GET /api/*` (proxied to rosbag-manager) | phase 4.2 |
| `WS /ws/topics`, `/ws/camera`, `/ws/health` | phase 4.4+ |

| Page | Status |
|---|---|
| Home | live |
| Live | phase 4.4 |
| Bags | phase 4.3 |
| Record / Replay | phase 4.5 |
| Pipelines | phase 4.8 |
| Health | phase 4.6 |

## Layout

```
services/dashboard/
├── Dockerfile            multi-stage (node build → ros:humble runtime)
├── entrypoint.sh
├── backend/
│   ├── main.py           FastAPI app, /healthz, SPA fallback
│   ├── config.py         env-driven config
│   └── auth.py           HTTP Basic (reuses BAG_WEB_USER / BAG_WEB_PASS)
└── frontend/             React + Vite + TS
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx       nav + routes
        ├── styles.css
        └── pages/        Home / Bags / Live / Record / Replay / Pipelines / Health
```

## Configuration

| Env | Default | Description |
|---|---|---|
| `DASHBOARD_BIND` | `0.0.0.0` | Bind address. |
| `DASHBOARD_PORT` | `8090` | Bind port. Moves to `8089` in phase 4.3. |
| `BAG_WEB_USER` | (unset) | HTTP Basic username. Same value as the bag-web service. |
| `BAG_WEB_PASS` | (unset) | HTTP Basic password. Same value as the bag-web service. Both must be set or both unset (auth disabled). |
| `ROSBAG_MANAGER_URL` | `http://127.0.0.1:8086` | Where the proxy layer forwards bag-plane requests. |

## Inspecting

```bash
docker compose logs -f dashboard
curl -sS localhost:8090/healthz
```

If `BAG_WEB_USER` is set, browser requests need credentials.
