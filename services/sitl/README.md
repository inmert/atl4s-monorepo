# sitl

ArduPilot SITL — ArduCopter simulator producing a MAVLink stream identical to the target drone.

## Outputs

- UDP `127.0.0.1:14550` — primary stream (consumed by `mavros`)
- UDP `127.0.0.1:14551` — secondary (for MAVProxy or other tools)

## Configuration

| Env | Default | Description |
|---|---|---|
| `SITL_HOME_LAT` | `37.6213` | Home latitude |
| `SITL_HOME_LON` | `-122.3790` | Home longitude |
| `SITL_HOME_ALT` | `5` | Home altitude (m) |
| `SITL_HOME_HEADING` | `0` | Home heading (deg) |

## Build

First build compiles ArduPilot from source. Expect 15–25 minutes.

## Activation

Only starts under the `sim` profile (`docker compose --profile sim up`).
