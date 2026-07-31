"""Lambda behind API Gateway: serve prediction data from the private S3 bucket.

Two routes, one function:
    GET /predictions          the fleet snapshot (one row per engine)
    GET /history?engine=<id>  one engine's full per-cycle degradation history

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
"""

from __future__ import annotations

import json
import os

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]
KEY = os.environ.get("KEY", "predictions/predictions.json")
HISTORY_PREFIX = os.environ.get("HISTORY_PREFIX", "predictions/history").rstrip("/")

# CORS so a browser app on another origin (e.g. Vercel) can fetch this.
HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-cache",
}

# A given engine's history only changes when the pipeline reruns, so unlike the
# fleet snapshot it is worth letting the browser hold on to.
HISTORY_HEADERS = {**HEADERS, "Cache-Control": "public, max-age=3600"}


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
            key, headers = _history_key(event), HISTORY_HEADERS
        except ValueError as exc:
            return _error(400, str(exc))
    else:
        key, headers = KEY, HEADERS

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return _response(200, obj["Body"].read().decode("utf-8"), headers)
    except s3.exceptions.NoSuchKey:
        return _error(404, f"{key} not found — run train.py --s3 / history.py --s3 first")
    except Exception as exc:  # noqa: BLE001 — surface any AWS error as JSON
        return _error(500, str(exc))
