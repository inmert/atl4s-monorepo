# Deployment

## VM specifications

See `README.md`.

## Manual provisioning steps

To be replaced by Terraform in `deploy/gcp/`.

1. Create G2 VM with 1× L4 in `northamerica-northeast1-c`, Ubuntu 22.04, 500 GB SSD persistent disk.
2. Firewall: keep `default-allow-ssh`, `default-allow-icmp`, `default-allow-internal`. Add `allow-foxglove-test` (TCP 8765, source `0.0.0.0/0` — to be tightened).
3. Install NVIDIA driver: `python3 cuda_installer.pyz install_driver` (production branch).
4. Install Docker (`get.docker.com`) and NVIDIA Container Toolkit.
5. Add user to `docker` group, reconnect.
6. Clone this repo, `cp .env.example .env`, edit as needed.

## Running

```bash
./scripts/dev-up.sh        # SITL + downstream
./scripts/prod-up.sh       # real drone + downstream
docker compose logs -f
docker compose down
```

## Cost discipline

Stop the VM when idle:

```bash
gcloud compute instances stop arachnid-atl4s-vm \
  --zone=northamerica-northeast1-c
```

Running cost: ~$17/day on-demand. Stopped cost: ~$0.07/day (disk only).
