"""Batch pipeline: fetch images from S3, process with vision agent, write JSON to output S3.

Usage:
    uv run python scripts/batch_run.py --output-prefix <model-name> --limit <max-images>

Example:
    uv run python scripts/batch_run.py --output-prefix claude-sonnet-4.6 --limit 100

Outputs are written to:
    s3://{S3_OUTPUT_BUCKET}/{output_prefix}/{image_key_without_ext}.json

Failures are written to:
    s3://{S3_OUTPUT_BUCKET}/failures/{output_prefix}/{image_key_without_ext}.json

Re-running is safe: images whose output already exists are skipped.
"""

import argparse
import json
import logging
import pathlib

import boto3
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from maplerugs.config import settings
from maplerugs.pipeline import process_image

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _output_key(prefix: str, image_key: str) -> str:
    return f"{prefix}/{pathlib.Path(image_key).with_suffix('.json')}"


def _failure_key(prefix: str, image_key: str) -> str:
    return f"failures/{prefix}/{pathlib.Path(image_key).with_suffix('.json')}"


def _output_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def _fetch_image(s3, bucket: str, key: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _write_json(s3, bucket: str, key: str, data: dict) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, indent=2),
        ContentType="application/json",
    )


@retry(wait=wait_exponential_jitter(initial=1, max=60), stop=stop_after_attempt(3))
def _process_with_retry(image_bytes: bytes, filename: str):
    return process_image(image_bytes, filename=filename)


def run(output_prefix: str, limit: int | None = None) -> None:
    session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)
    s3 = session.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    image_keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=settings.s3_input_bucket)
        for obj in page.get("Contents", [])
        if pathlib.Path(obj["Key"]).suffix.lower() in _IMAGE_EXTENSIONS
    ]
    logger.info("Found %d images in %s", len(image_keys), settings.s3_input_bucket)

    if limit is not None:
        image_keys = image_keys[:limit]
        logger.info("Limiting to %d image(s)", limit)

    completed = skipped = failed = 0

    for key in image_keys:
        out_key = _output_key(output_prefix, key)

        if _output_exists(s3, settings.s3_output_bucket, out_key):
            logger.info("skip %s", key)
            skipped += 1
            continue

        try:
            image_bytes = _fetch_image(s3, settings.s3_input_bucket, key)
            record = _process_with_retry(image_bytes, filename=key)
            _write_json(s3, settings.s3_output_bucket, out_key, record.model_dump())
            logger.info("ok   %s → %s", key, out_key)
            completed += 1
        except Exception as exc:
            logger.error("fail %s: %s", key, exc)
            _write_json(
                s3,
                settings.s3_output_bucket,
                _failure_key(output_prefix, key),
                {"key": key, "error": str(exc)},
            )
            failed += 1

    logger.info("Done — completed: %d, skipped: %d, failed: %d", completed, skipped, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-prefix",
        required=True,
        help="S3 prefix for output files (e.g. claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N images (for testing)",
    )
    args = parser.parse_args()
    run(args.output_prefix, limit=args.limit)
