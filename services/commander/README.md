# commander

Autonomy node. Subscribes to MAVROS telemetry, applies decision logic, calls MAVROS services for the response.

## Behavior

Subscribes to `/mavros/state` and `/mavros/battery` with Best Effort QoS.

- Logs the initial state, then every transition in `connected`, `mode`, or `armed`.
- When `battery.percentage <= BATTERY_LOW_THRESHOLD`, calls `/mavros/set_mode` with `custom_mode=RTL` and latches. Clears the latch once `percentage > threshold + 5%` (hysteresis avoids flapping near the trip point).

## Configuration

| Env | Default | Description |
|---|---|---|
| `BATTERY_LOW_THRESHOLD` | `0.20` | Normalized battery percentage at or below which RTL fires. |

## Inspecting

```bash
docker compose logs -f commander
```

## Smoke test

Force a trip without waiting for a real low-battery event by raising the threshold above the current SITL battery (100%):

```bash
BATTERY_LOW_THRESHOLD=1.0 docker compose --profile sim up -d --force-recreate commander
docker compose logs --tail 20 commander
```

Expect: `Battery low: 100.0% <= 100% (12.60 V). Triggering RTL.` followed by `set_mode RTL accepted.` and a mode transition in `/mavros/state`. Reset with `BATTERY_LOW_THRESHOLD=0.20 docker compose --profile sim up -d --force-recreate commander`.
