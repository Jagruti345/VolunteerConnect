"""
Key pair automation.
Creates an EC2 key pair and saves the .pem locally with correct permissions.
If a local .pem already exists we assume the pair is already set up and skip
recreating it (AWS never lets you re-download a private key).
"""

import os
import stat
import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, KEY_NAME, KEY_FILE
from modules.logger import write_success, write_warn, write_error

ec2 = boto3.client("ec2", region_name=AWS_REGION)


def create_key_pair():
    if os.path.exists(KEY_FILE):
        write_warn(f"Key file '{KEY_FILE}' already exists locally, reusing it.")
        return KEY_NAME

    try:
        # If the key exists in AWS but not locally, we can't recover the
        # private material - delete and recreate so provisioning can proceed.
        try:
            ec2.describe_key_pairs(KeyNames=[KEY_NAME])
            write_warn(f"Key pair '{KEY_NAME}' exists in AWS but not locally. Recreating.")
            ec2.delete_key_pair(KeyName=KEY_NAME)
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("InvalidKeyPair.NotFound",):
                raise

        response = ec2.create_key_pair(KeyName=KEY_NAME, KeyType="rsa", KeyFormat="pem")

        with open(KEY_FILE, "w") as f:
            f.write(response["KeyMaterial"])

        os.chmod(KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)  # chmod 600
        write_success(f"Key pair '{KEY_NAME}' created and saved to {KEY_FILE}")
        return KEY_NAME
    except ClientError as e:
        write_error(f"Key pair creation failed: {e}")
        raise
