# uploader — watches /data/bags for completed bag directories and pushes
# them to gs://${GCS_BUCKET}. On the VM, the GCE metadata server provides
# credentials for the atl4s-vm-sa service account (no key file). On the
# Orin Nano (Phase 5) mount a service-account JSON at /gcp-key.json and
# set GOOGLE_APPLICATION_CREDENTIALS.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir google-cloud-storage==2.18.2

ENV BAG_DIR=/data/bags
ENV GCS_BUCKET=atl4s-rosbags
ENV STABLE_SECONDS=15
ENV POLL_SECONDS=10

COPY uploader.py /uploader.py

CMD ["python", "/uploader.py"]
