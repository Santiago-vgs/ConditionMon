"""Deploy (or tear down) the predictions REST API on AWS.

Creates three things, all named with PREFIX so they're easy to find/delete:
    1. an IAM execution role the Lambda assumes (least-privilege: read ONE S3 object + logs)
    2. the Lambda function (api/handler.py)
    3. an API Gateway HTTP API with `GET /predictions` -> Lambda, CORS enabled

Usage:
    python api/deploy.py            # create / update everything, print the URL
    python api/deploy.py --delete   # remove everything it created

Requires AWS credentials with Lambda + API Gateway + IAM permissions (more than
the S3-only `turbofan-cli` user — see the deploy notes). Pick the identity with
the AWS_PROFILE env var, e.g.:  AWS_PROFILE=turbofan-admin python api/deploy.py
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
BUCKET = "svargas-turbofan-pm"
KEY = "predictions/predictions.json"
HISTORY_PREFIX = "predictions/history"

PREFIX = "turbofan-predictions"
ROLE_NAME = f"{PREFIX}-lambda-role"
FUNCTION_NAME = f"{PREFIX}-api"
API_NAME = f"{PREFIX}-http-api"
ROUTES = ("GET /predictions", "GET /history")
HANDLER_FILE = Path(__file__).resolve().parent / "handler.py"

iam = boto3.client("iam", region_name=REGION)
lam = boto3.client("lambda", region_name=REGION)
api = boto3.client("apigatewayv2", region_name=REGION)
sts = boto3.client("sts", region_name=REGION)

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}


def s3_read_policy() -> dict:
    """Least privilege: read the snapshot and the per-engine histories, plus
    write CloudWatch logs.

    The history grant has to be a prefix wildcard (one object per engine), so it
    is scoped to `predictions/history/` alone rather than the whole bucket —
    the raw data and model artifacts stay unreadable by this function.
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": [
                    f"arn:aws:s3:::{BUCKET}/{KEY}",
                    f"arn:aws:s3:::{BUCKET}/{HISTORY_PREFIX}/*",
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": "arn:aws:logs:*:*:*",
            },
        ],
    }


# ------------------------------------------------------------------ role
def ensure_role() -> str:
    try:
        role = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description="Execution role for the turbofan predictions API Lambda",
        )["Role"]
        print(f"  created role {ROLE_NAME}")
        time.sleep(10)  # let the new role propagate before Lambda uses it
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
        print(f"  role {ROLE_NAME} already exists")
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName=f"{PREFIX}-s3-read",
        PolicyDocument=json.dumps(s3_read_policy()),
    )
    return role["Arn"]


# ------------------------------------------------------------------ lambda
def zip_handler() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(HANDLER_FILE, arcname="handler.py")
    return buf.getvalue()


def ensure_function(role_arn: str) -> str:
    code = zip_handler()
    env = {"Variables": {
        "BUCKET": BUCKET, "KEY": KEY, "HISTORY_PREFIX": HISTORY_PREFIX,
    }}
    try:
        fn = lam.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.13",
            Role=role_arn,
            Handler="handler.handler",
            Code={"ZipFile": code},
            Timeout=10,
            MemorySize=128,
            Environment=env,
            Description="Serves predictions.json from S3 with CORS",
        )
        print(f"  created function {FUNCTION_NAME}")
    except lam.exceptions.ResourceConflictException:
        lam.update_function_code(FunctionName=FUNCTION_NAME, ZipFile=code)
        lam.get_waiter("function_updated").wait(FunctionName=FUNCTION_NAME)
        lam.update_function_configuration(FunctionName=FUNCTION_NAME, Environment=env)
        fn = lam.get_function_configuration(FunctionName=FUNCTION_NAME)
        print(f"  updated function {FUNCTION_NAME}")
    return fn["FunctionArn"]


# ------------------------------------------------------------------ api gateway
def ensure_api(function_arn: str) -> str:
    existing = next((a for a in api.get_apis()["Items"] if a["Name"] == API_NAME), None)
    if existing:
        api_id = existing["ApiId"]
        print(f"  api {API_NAME} already exists ({api_id})")
    else:
        created = api.create_api(
            Name=API_NAME,
            ProtocolType="HTTP",
            CorsConfiguration={
                "AllowOrigins": ["*"],
                "AllowMethods": ["GET", "OPTIONS"],
                "AllowHeaders": ["content-type"],
            },
        )
        api_id = created["ApiId"]
        print(f"  created api {API_NAME} ({api_id})")

    # Reuse the existing integration if one already points at this function —
    # creating a new one on every deploy would leave orphan integrations behind.
    integration = next(
        (i["IntegrationId"] for i in api.get_integrations(ApiId=api_id)["Items"]
         if i.get("IntegrationUri") == function_arn),
        None,
    )
    if integration is None:
        integration = api.create_integration(
            ApiId=api_id,
            IntegrationType="AWS_PROXY",
            IntegrationUri=function_arn,
            PayloadFormatVersion="2.0",
        )["IntegrationId"]
        print(f"  created integration {integration}")
    else:
        print(f"  reusing integration {integration}")

    routes = {r["RouteKey"]: r for r in api.get_routes(ApiId=api_id)["Items"]}
    for route in ROUTES:
        if route in routes:
            print(f"  route {route} already exists")
            continue
        api.create_route(ApiId=api_id, RouteKey=route, Target=f"integrations/{integration}")
        print(f"  created route {route}")

    # auto-deploy default stage
    try:
        api.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)
    except ClientError:
        pass  # stage already exists

    # Allow API Gateway to invoke the function on any route of *this* api. An
    # earlier version pinned this to /predictions, which silently 403s every
    # route added later — so on conflict the old statement is replaced rather
    # than left in place.
    account = sts.get_caller_identity()["Account"]
    source_arn = f"arn:aws:execute-api:{REGION}:{account}:{api_id}/*/*"
    statement_id = f"{PREFIX}-apigw-invoke"
    for attempt in (1, 2):
        try:
            lam.add_permission(
                FunctionName=FUNCTION_NAME,
                StatementId=statement_id,
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=source_arn,
            )
            break
        except lam.exceptions.ResourceConflictException:
            if attempt == 2:
                raise
            lam.remove_permission(FunctionName=FUNCTION_NAME, StatementId=statement_id)
            print("  replaced stale invoke permission")

    base = f"https://{api_id}.execute-api.{REGION}.amazonaws.com"
    print(f"  history:     {base}/history?engine=1")
    return f"{base}/predictions"


# ------------------------------------------------------------------ teardown
def delete_all() -> None:
    for a in (x for x in api.get_apis()["Items"] if x["Name"] == API_NAME):
        api.delete_api(ApiId=a["ApiId"])
        print(f"  deleted api {a['ApiId']}")
    try:
        lam.delete_function(FunctionName=FUNCTION_NAME)
        print(f"  deleted function {FUNCTION_NAME}")
    except lam.exceptions.ResourceNotFoundException:
        pass
    try:
        for p in iam.list_role_policies(RoleName=ROLE_NAME)["PolicyNames"]:
            iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName=p)
        iam.delete_role(RoleName=ROLE_NAME)
        print(f"  deleted role {ROLE_NAME}")
    except iam.exceptions.NoSuchEntityException:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="tear everything down")
    args = parser.parse_args()

    print(f"Identity: {sts.get_caller_identity()['Arn']}")
    if args.delete:
        delete_all()
        return 0

    print("1. IAM execution role:")
    role_arn = ensure_role()
    print("2. Lambda function:")
    fn_arn = ensure_function(role_arn)
    print("3. API Gateway HTTP API:")
    url = ensure_api(fn_arn)
    print(f"\nDeployed.  GET {url}")
    print("Test it:  curl " + url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
