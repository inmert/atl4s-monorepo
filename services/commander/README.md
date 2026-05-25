# commander

Autonomy node — subscribes to telemetry, applies decision logic, publishes commands back to MAVROS as behaviors are added.

## v1 (current)

Subscribes to `/mavros/state` and `/mavros/battery` with Best Effort QoS and logs:

- Initial state (connection, mode, armed) and subsequent transitions
- Battery threshold crossings (warns once when `percentage <= threshold`; logs recovery once above `threshold + 5%` hysteresis)

No commands sent yet.

## v2 (planned)

On low-battery latch *and* `armed == true`, calls the `/mavros/set_mode` service with `custom_mode=RTL`.

## Configuration

| Env | Default | Description |
|---|---|---|
| `BATTERY_LOW_THRESHOLD` | `0.20` | Normalized battery percentage at or below which the low-battery warning fires. |

## Inspecting

```bash
docker compose logs -f commander
```

Manual smoke test for the battery branch (drop the threshold above the current SITL battery level so the warning fires immediately):

```bash
BATTERY_LOW_THRESHOLD=1.0 docker compose --profile sim up -d --force-recreate commander
docker compose logs --tail 20 commander
```
