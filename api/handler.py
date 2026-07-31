"""Lambda behind API Gateway: serve prediction data from the private S3 bucket.

Three routes, one function:
    GET /predictions          the fleet snapshot (one row per engine)
    GET /history?engine=<id>  one engine's full per-cycle degradation history
    GET /metrics              model-health metrics from insights.py

The bucket stays fully private — only this function can read it (its execution
role grants s3:GetObject under the predictions/ prefix, nothing else). The
browser dashboard calls the API Gateway URL, never S3 directly.

History is served per engine rather than as one fleet-wide blob so the dashboard
transfers ~4 KB to draw one chart instead of ~1.8 MB for all 100. That makes the
engine id caller-controlled, so it is parsed as an int and re-formatted into the
key — passing the raw string through would let a caller walk the prefix.

Env vars (set at deploy time):
    BUCKET         the S3 bucket name
    KEY            fleet snapshot key (default: predictions/predictions.json)
    HISTORY_PREFIX per-engine history prefix (default: predictions/history)
    METRICS_KEY    model-health metrics key (default: predictions/metrics.json)
"""

from __future__ import annotations

import json
import os

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]
KEY = os.environ.get("KEY", "predictions/predictions.json")
HISTORY_PREFIX = os.environ.get("HISTORY_PREFIX", "predictions/history").rstrip("/")
METRICS_KEY = os.environ.get("METRICS_KEY", "predictions/metrics.json")

# CORS so a browser app on another origin (e.g. Vercel) can fetch this.
HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-cache",
}

# History and metrics only change when the pipeline reruns, so unlike the fleet
# snapshot they are worth letting the browser hold on to.
CACHEABLE_HEADERS = {**HEADERS, "Cache-Control": "public, max-age=3600"}


def _response(status: int, body: str, headers: dict | None = None) -> dict:
    return {"statusCode": status, "headers": headers or HEADERS, "body": body}


def _error(status: int, message: str) -> dict:
    return _response(status, json.dumps({"error": message}))


def _history_key(event) -> str:
    """Resolve ?engine=<id> to an S3 key, rejecting anything not an integer."""
    params = event.get("queryStringParameters") or {}
    raw = params.get("engine")
    if raw is None:
        raise ValueError("missing required query parameter 'engine'")
    try:
        engine_id = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"engine must be an integer, got {raw!r}") from None
    if engine_id < 1:
        raise ValueError(f"engine must be positive, got {engine_id}")
    return f"{HISTORY_PREFIX}/engine_{engine_id}.json"


def handler(event, context):  # noqa: ANN001 (AWS signature)
    path = (event.get("rawPath") or "/predictions").rstrip("/")

    if path.endswith("/history"):
        try:
            key, headers = _history_key(event), CACHEABLE_HEADERS
        except ValueError as exc:
            return _error(400, str(exc))
    elif path.endswith("/metrics"):
        key, headers = METRICS_KEY, CACHEABLE_HEADERS
    else:
        key, headers = KEY, HEADERS

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return _response(200, obj["Body"].read().decode("utf-8"), headers)
    except ClientError as exc:
        # The role deliberately has no s3:ListBucket, so S3 answers AccessDenied
        # rather than NoSuchKey for a key that isn't there — an unknown engine id
        # arrives here, not in a 404 branch keyed on NoSuchKey.
        code = exc.response.get("Error", {}).get("Code", "")
        print(f"s3 get_object failed for {key}: {code}: {exc}")  # -> CloudWatch
        if code in ("NoSuchKey", "AccessDenied", "NoSuchBucket", "404"):
            return _error(404, "not found")
        return _error(500, "internal error")
    except Exception as exc:  # noqa: BLE001
        # Never echo the raw error: it carries the account id, role ARN and
        # bucket name, and this endpoint is public.
        print(f"unexpected error serving {key}: {exc!r}")  # -> CloudWatch
        return _error(500, "internal error")
