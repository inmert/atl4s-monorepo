# console

The ATL4S operator dashboard. It **runs natively on the host** (not in a container) as the `atl4s-console` systemd service, because it manages the Docker stack itself (container lifecycle, the Docker socket) and shouldn't live inside the stack it controls. It replaced the old `services/dashboard` container.

## Logic / design split

The defining rule: the **logic layer** (FastAPI) and the **design layer** (React) only talk over HTTP/JSON.

```
console/
├── api/          logic layer — FastAPI (auth, containers, deployments, serves the SPA)
│   ├── main.py       routes + SPA fallback
│   ├── auth.py       session login (signed httpOnly cookie)
│   ├── containers.py Docker control: list / inspect / logs / stats / start·stop·restart / env edit
│   ├── deployments.py robot/vehicle/sensor registry (CRUD → config/deployments.yaml)
│   └── config.py     host-relative paths (ui/dist, config/)
├── ui/           design layer — React + Vite + TS (built to ui/dist)
│   └── src/
│       ├── lib/api.ts    the ONLY seam to the backend (fetch lives here)
│       ├── lib/…         auth / theme / nav / deployments helpers
│       ├── styles/       tokens.css (typeui "dashboard" system) + app.css
│       ├── components/   Drawer, Modal, StatusBadge, LiveLogs, …
│       └── pages/        Login, Shell, Containers, Deployments, … (placeholders for the rest)
├── config/       runtime config (read/written by the console)
│   ├── deployments.yaml                  deployment registry
│   └── pipelines/perception-lidar.yaml   (also bind-mounted RO into perception-lidar)
├── requirements.txt
├── deploy/atl4s-console.service.template   systemd unit (installer fills in paths)
└── scripts/      build-ui.sh · setup.sh · run.sh · install-service.sh
```

## Why on the host

- It controls Docker via the local socket — as `arachnid` (in the `docker` group), no mounted socket needed.
- It outlives `docker compose down`; restarting the stack never restarts the console.
- ROS is installed on the host, so future telemetry features can use `rclpy` directly.

## Setup (first time)

```bash
cd console
./scripts/setup.sh            # builds ui/dist via an ephemeral node:20 container,
                              # creates .venv, installs requirements.txt
./scripts/install-service.sh  # installs + starts the atl4s-console systemd service
```

`setup.sh` needs Docker (for the UI build) and `python3-venv`. No Node on the host.

## Running

| | |
|---|---|
| Service | `sudo systemctl {status,restart,stop} atl4s-console` |
| Logs | `journalctl -u atl4s-console -f` |
| Foreground (dev) | `console/scripts/run.sh` |
| UI dev server | `cd ui && npm run dev` (proxies `/api` + `/ws` to `:8089`) |
| Rebuild UI after a change | `console/scripts/build-ui.sh` then `sudo systemctl restart atl4s-console` |

Listens on `:8089`. Open `http://<VM_external_IP>:8089/`.

## Auth

Form login (not the browser Basic dialog), reusing `BAG_WEB_USER` / `BAG_WEB_PASS` from the repo `.env` (the systemd unit loads it via `EnvironmentFile`):

- `GET /api/auth/me`, `POST /api/auth/login`, `POST /api/auth/logout`.
- Signed, httpOnly session cookie (HMAC, 7-day TTL); secret derived from the credentials so sessions survive a restart. With both vars unset, auth is disabled (closed-firewall only).

## Configuration

| Env | Default | Description |
|---|---|---|
| `CONSOLE_BIND` | `0.0.0.0` | Bind address. |
| `CONSOLE_PORT` | `8089` | Bind port. |
| `CONSOLE_STATIC_DIR` | `console/ui/dist` | Built SPA. |
| `DEPLOYMENTS_CONFIG` | `console/config/deployments.yaml` | Deployment registry path. |
| `CONTAINERS_NAME_PREFIX` | `atl4s-` | Only containers with this prefix are listed/controlled. |
| `CONSOLE_SESSION_SECRET` | derived | Override the cookie signing secret. |

## Design system

typeui.sh **"dashboard"** — dark cloud-platform aesthetic (primary `#0C5CAB`, near-black surfaces, IBM Plex Sans, 8pt grid, glass panels) with a light/dark toggle. Spec installed as a Claude Code skill at [`.claude/skills/design-system/SKILL.md`](../.claude/skills/design-system/SKILL.md); follow it when adding UI.
