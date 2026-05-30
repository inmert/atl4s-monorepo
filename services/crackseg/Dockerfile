# crackseg — UNet crack-segmentation inference (yakhyo/crack-segmentation, MIT).
# CUDA torch base (runs on the L4; falls back to CPU if no GPU is present).
# Loopback-only backend; the console proxies to it and the inspector overlays
# its output.

FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir \
        fastapi==0.115.5 \
        "uvicorn[standard]==0.32.0" \
        python-multipart==0.0.12 \
        pyyaml==6.0.2 \
        pillow==10.4.0 \
        numpy==1.26.4 \
        opencv-python-headless==4.10.0.84

# Pretrained UNet checkpoints (~62 MB each), one per training loss.
RUN mkdir -p /app/weights && python - <<'PY'
import urllib.request
base = "https://github.com/yakhyo/crack-segmentation/releases/download/v0.0.1"
for v in ("ce", "dice", "dicece", "focal"):
    print("downloading", v)
    urllib.request.urlretrieve(f"{base}/{v}.pt", f"/app/weights/{v}.pt")
PY

# crackseg/ must stay importable at this path so torch.load can unpickle the
# checkpoints (they pickle crackseg.models.unet.* instances).
COPY crackseg/ /app/crackseg/
COPY app/ /app/app/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV CRACKSEG_BIND=127.0.0.1 \
    CRACKSEG_PORT=8092 \
    CRACKSEG_WEIGHTS_DIR=/app/weights \
    CRACKSEG_CONFIG=/app/config/pipelines/crackseg.yaml

CMD ["/entrypoint.sh"]
