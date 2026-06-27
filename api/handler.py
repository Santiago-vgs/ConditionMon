"""Lambda behind API Gateway: serve predictions.json from the private S3 bucket.

The bucket stays fully private — only this function can read it (its execution
role grants s3:GetObject on the single predictions object, nothing else). The
browser dashboard calls the API Gateway URL, never S3 directly.

Env vars (set at deploy time):
    BUCKET   the S3 bucket name
    KEY      object key (default: predictions/predictions.json)
"""

from __future__ import annotations

import json
import os

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["BUCKET"]
KEY = os.environ.get("KEY", "predictions/predictions.json")

# CORS so a browser app on another origin (e.g. Vercel) can fetch this.
HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-cache",
}


def handler(event, context):  # noqa: ANN001 (AWS signature)
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=KEY)
        body = obj["Body"].read().decode("utf-8")
        return {"statusCode": 200, "headers": HEADERS, "body": body}
    except s3.exceptions.NoSuchKey:
        return {
            "statusCode": 404,
            "headers": HEADERS,
            "body": json.dumps({"error": f"{KEY} not found — run train.py --s3 first"}),
        }
    except Exception as exc:  # noqa: BLE001 — surface any AWS error as JSON
        return {
            "statusCode": 500,
            "headers": HEADERS,
            "body": json.dumps({"error": str(exc)}),
        }
