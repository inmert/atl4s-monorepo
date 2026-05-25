# sitl

ArduCopter SITL configured to take its flight dynamics from the external Gazebo simulator (services/gazebo), not the internal model. MAVLink stream is identical to the target drone.

## Internals

Two processes inside the container:

1. `arducopter --model JSON` — MAVLink master on TCP `127.0.0.1:5760`. Sensor data (IMU, GPS, baro) comes from Gazebo over UDP 9002 (JSON FDM). Actuator commands are sent back to Gazebo on the same channel.
2. `mavproxy.py` — connects to the TCP master and forwards MAVLink over UDP.

The entrypoint launches both, then `wait -n` exits the container if either dies so the supervisor restarts the whole unit.

The container `depends_on: gazebo` so Gazebo comes up first. If `atl4s-gazebo` isn't running, ArduCopter will retry the JSON FDM connection forever and never reach `ArduPilot Ready`.

## Output

| Endpoint | Direction | Consumer |
|---|---|---|
| TCP `127.0.0.1:5760` | listening | MAVProxy (in-container) |
| UDP `127.0.0.1:14550` | bidirectional (`udp:`) | `mavros` |

`network_mode: host`, so `127.0.0.1` is the VM loopback. MAVProxy uses `udp:` so MAVROS commands round-trip back to ArduPilot. Use `udpout:` only for an explicitly send-only channel.

## Configuration

| Env | Default | Description |
|---|---|---|
| `SITL_HOME_LAT` | `37.6213` | Home latitude |
| `SITL_HOME_LON` | `-122.3790` | Home longitude |
| `SITL_HOME_ALT` | `5` | Home altitude (m) |
| `SITL_HOME_HEADING` | `0` | Home heading (deg) |
| `SITL_SPEEDUP` | `1` | (Unused with `--model JSON`; Gazebo's `real_time_factor` controls sim time.) |
| `MAVPROXY_OUT` | `udp:127.0.0.1:14550` | MAVProxy `--out` target. `udp:` is bidirectional (commands round-trip); `udpout:` is send-only. |
| `MAVPROXY_STREAMRATE` | `10` | MAVProxy `--streamrate`. Rate (Hz) at which MAVProxy requests data streams from ArduPilot via `MAV_CMD_REQUEST_DATA_STREAM`; drives `/mavros/*` topic rates. ArduPilot rate-limits below the request; observed `/mavros/imu/data` at ~5 Hz with `--streamrate 10`. |

## Defaults

ArduCopter is launched with `--defaults copter.parm,gazebo-iris.parm`. The `gazebo-iris.parm` file (shipped with the ArduPilot tree) configures `FRAME_CLASS`, `FRAME_TYPE`, the sonar/rangefinder for IRLock, and the parameters expected by the Gazebo iris model.

ArduCopter 4.8 removed the `SR0_*` per-channel stream-rate params for SERIAL0 (the channel SITL uses) — `MAVPROXY_STREAMRATE` is now the only knob.

## Build

First build compiles ArduPilot from source (15–25 min). Subsequent builds use the Docker layer cache.

## Activation

Only starts under the `sim` profile:

```bash
docker compose --profile sim up -d sitl
```

`dev-up.sh` includes the profile; `prod-up.sh` does not.
