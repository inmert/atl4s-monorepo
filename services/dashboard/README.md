# dashboard

Single human-facing surface for ATL4S. React + Vite + TS frontend, FastAPI + rclpy backend, served from one container. HTTP Basic on TCP 8089.

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
| Bags | live — list / files / upload / download / delete via the proxy |
| Live | phase 4.4 |
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
| `DASHBOARD_PORT` | `8089` | Bind port. |
| `BAG_WEB_USER` | (unset) | HTTP Basic username. Env-var name kept stable from bag-web for `.env` compatibility. |
| `BAG_WEB_PASS` | (unset) | HTTP Basic password. Both must be set or both unset (auth disabled — only safe behind a closed firewall). |
| `ROSBAG_MANAGER_URL` | `http://127.0.0.1:8086` | Where the proxy layer forwards bag-plane requests. |

## Inspecting

```bash
docker compose logs -f dashboard
curl -sS localhost:8089/healthz
```

If `BAG_WEB_USER` is set, browser requests need credentials.
