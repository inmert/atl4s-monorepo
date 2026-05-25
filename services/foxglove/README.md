# foxglove

Foxglove Bridge — exposes ROS 2 topics over a WebSocket so a browser-based [Foxglove Studio](https://studio.foxglove.dev/) client can subscribe to them.

## Output

| Endpoint | Direction | Consumer |
|---|---|---|
| TCP `0.0.0.0:8765` | listening | Foxglove Studio (browser) |

Container uses `network_mode: host`, so the port binds on the VM's external interface directly. QoS is auto-negotiated per topic, so `/mavros/*` (Best Effort) is handled without extra configuration.

## Configuration

| Env | Default | Description |
|---|---|---|
| `FOXGLOVE_PORT` | `8765` | WebSocket port |
| `FOXGLOVE_ADDRESS` | `0.0.0.0` | Bind address |

## Connecting

In Foxglove Studio:

1. Open `https://studio.foxglove.dev/`.
2. Click "Open connection".
3. Choose "Foxglove WebSocket" and enter `ws://<VM_external_IP>:8765`.

The GCP firewall rule `allow-foxglove-test` (TCP 8765 from `0.0.0.0/0`) must be in place. This rule is intentionally permissive for the test phase and should be tightened before production exposure.
