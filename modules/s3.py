"""
S3 automation.
Creates the website bucket (idempotent) and uploads everything in app/,
guessing content types so HTML/CSS/JS/images are served correctly.
"""

import os
import mimetypes
import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, BUCKET_NAME, APP_DIR, APP_EXCLUDE_PREFIXES
from modules.logger import write_success, write_warn, write_error

s3 = boto3.client("s3", region_name=AWS_REGION)


def create_bucket():
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        write_warn(f"S3 bucket '{BUCKET_NAME}' already exists, reusing it.")
        return BUCKET_NAME
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code not in (404,):
            raise

    try:
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(
                Bucket=BUCKET_NAME,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )
        s3.put_public_access_block(
            Bucket=BUCKET_NAME,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        write_success(f"S3 bucket '{BUCKET_NAME}' created (private - EC2 reads via IAM role)")
        return BUCKET_NAME
    except ClientError as e:
        write_error(f"Bucket creation failed: {e}")
        raise


def upload_website():
    if not os.path.isdir(APP_DIR):
        write_error(f"'{APP_DIR}' directory not found - nothing to upload.")
        raise FileNotFoundError(APP_DIR)

    local_keys = set()
    uploaded = 0
    for root, _, files in os.walk(APP_DIR):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_key = os.path.relpath(local_path, APP_DIR).replace(os.sep, "/")

            if relative_key.startswith(APP_EXCLUDE_PREFIXES):
                continue

            local_keys.add(relative_key)
            content_type, _ = mimetypes.guess_type(local_path)
            extra_args = {"ContentType": content_type} if content_type else {}

            s3.upload_file(local_path, BUCKET_NAME, relative_key, ExtraArgs=extra_args)
            uploaded += 1

    write_success(f"Uploaded {uploaded} website file(s) to S3 bucket '{BUCKET_NAME}'")

    # Mirror mode: remove any objects in the bucket that no longer exist
    # locally, so leftover files from earlier versions of the app don't
    # keep getting deployed to EC2 forever.
    remote_keys = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME):
        for obj in page.get("Contents", []):
            remote_keys.add(obj["Key"])

    stale_keys = remote_keys - local_keys
    if stale_keys:
        s3.delete_objects(
            Bucket=BUCKET_NAME,
            Delete={"Objects": [{"Key": k} for k in stale_keys]},
        )
        write_success(f"Removed {len(stale_keys)} stale file(s) from S3 (no longer in {APP_DIR}/)")

    return uploaded
