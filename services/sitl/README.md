# sitl

ArduPilot SITL — ArduCopter simulator producing a MAVLink stream identical to the target drone.

## Internals

Two processes inside the container:

1. `arducopter` — ArduPilot SITL binary, MAVLink master on TCP `127.0.0.1:5760`.
2. `mavproxy.py` — connects to the TCP master and fans the stream out over UDP.

The entrypoint launches both, then `wait -n` exits the container if either dies (so the supervisor can restart the whole unit cleanly).

## Output

| Endpoint | Direction | Consumer |
|---|---|---|
| TCP `127.0.0.1:5760` | listening | MAVProxy (in-container) |
| UDP `127.0.0.1:14550` | bidirectional (`udp:` from MAVProxy) | `mavros` |

The container uses `network_mode: host`, so `127.0.0.1` resolves to the VM loopback. MAVProxy uses `udp:` (bidirectional) — it binds a local ephemeral port, sends from it to MAVROS, and listens for replies on it. MAVROS commands round-trip back to ArduPilot. Use `udpout:` only if you explicitly want a send-only channel.

## Configuration

| Env | Default | Description |
|---|---|---|
| `SITL_HOME_LAT` | `37.6213` | Home latitude |
| `SITL_HOME_LON` | `-122.3790` | Home longitude |
| `SITL_HOME_ALT` | `5` | Home altitude (m) |
| `SITL_HOME_HEADING` | `0` | Home heading (deg) |
| `SITL_SPEEDUP` | `1` | Simulation speed multiplier |
| `MAVPROXY_OUT` | `udp:127.0.0.1:14550` | MAVProxy `--out` target (bidirectional) |

## Build

First build compiles ArduPilot from source. Expect 15–25 minutes. Subsequent builds use the Docker layer cache.

## Activation

Only starts under the `sim` profile:

```bash
docker compose --profile sim up -d sitl
```

`./scripts/dev-up.sh` includes the profile; `./scripts/prod-up.sh` does not.
