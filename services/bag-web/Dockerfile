# bag-web — FastAPI server for browsing/uploading/deleting rosbags in
# gs://${GCS_BUCKET}. Mirrors the uploader's GCS auth path: GCE metadata
# server on the VM (no key file).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
        fastapi==0.115.5 \
        uvicorn[standard]==0.32.0 \
        google-cloud-storage==2.18.2 \
        python-multipart==0.0.12 \
        jinja2==3.1.4

ENV GCS_BUCKET=atl4s-rosbags
ENV BAG_WEB_PORT=8089

WORKDIR /app
COPY bag_web.py /app/bag_web.py
COPY templates /app/templates
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8089/tcp

CMD ["/app/entrypoint.sh"]
