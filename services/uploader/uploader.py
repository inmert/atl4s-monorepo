"""Watch BAG_DIR for completed bags and upload each to GCS.

A bag is "completed" once no file inside it has been modified for
STABLE_SECONDS. After a successful upload, a sibling sentinel
`<bag>.uploaded` is created to suppress re-upload across restarts.
"""

import logging
import os
import time
from pathlib import Path

from google.cloud import storage


BAG_DIR = Path(os.environ.get('BAG_DIR', '/data/bags'))
GCS_BUCKET = os.environ['GCS_BUCKET']
STABLE_SECONDS = int(os.environ.get('STABLE_SECONDS', '15'))
POLL_SECONDS = int(os.environ.get('POLL_SECONDS', '10'))

log = logging.getLogger('uploader')
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def latest_mtime(directory: Path) -> float:
    return max(p.stat().st_mtime for p in directory.rglob('*') if p.is_file())


def upload_bag(bucket: storage.Bucket, bag: Path) -> int:
    count = 0
    for path in bag.rglob('*'):
        if not path.is_file():
            continue
        blob_name = f'{bag.name}/{path.relative_to(bag).as_posix()}'
        blob = bucket.blob(blob_name)
        if blob.exists():
            log.info('skip %s (already in gs://%s/%s)', path.name, GCS_BUCKET, blob_name)
            continue
        log.info('upload %s → gs://%s/%s', path.name, GCS_BUCKET, blob_name)
        blob.upload_from_filename(str(path))
        count += 1
    return count


def main() -> None:
    BAG_DIR.mkdir(parents=True, exist_ok=True)
    bucket = storage.Client().bucket(GCS_BUCKET)

    log.info('watching %s; target gs://%s (stable=%ds, poll=%ds)',
             BAG_DIR, GCS_BUCKET, STABLE_SECONDS, POLL_SECONDS)

    while True:
        for bag in sorted(p for p in BAG_DIR.iterdir() if p.is_dir()):
            sentinel = bag.parent / f'{bag.name}.uploaded'
            if sentinel.exists():
                continue
            try:
                age = time.time() - latest_mtime(bag)
            except ValueError:
                continue  # empty directory
            if age < STABLE_SECONDS:
                continue
            log.info('uploading %s (stable for %.0fs)', bag.name, age)
            try:
                n = upload_bag(bucket, bag)
                sentinel.touch()
                log.info('uploaded %s (%d files)', bag.name, n)
            except Exception as exc:
                log.error('upload failed for %s: %s', bag.name, exc)
        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
