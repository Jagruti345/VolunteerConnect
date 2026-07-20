"""
IAM automation.
Creates (idempotently) an EC2 IAM role that can read the S3 website bucket,
wraps it in an instance profile, and attaches it. Safe to run repeatedly:
every function checks whether the resource already exists before creating it.
"""

import json
import time
import boto3
from botocore.exceptions import ClientError

from config import (
    AWS_REGION,
    IAM_ROLE_NAME,
    IAM_POLICY_NAME,
    INSTANCE_PROFILE_NAME,
    BUCKET_NAME,
)
from modules.logger import write_success, write_warn, write_error

iam = boto3.client("iam", region_name=AWS_REGION)

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}


def create_role():
    try:
        iam.get_role(RoleName=IAM_ROLE_NAME)
        write_warn(f"IAM role '{IAM_ROLE_NAME}' already exists, reusing it.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        iam.create_role(
            RoleName=IAM_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description="Allows EC2 to read the VolunteerConnect S3 website bucket",
        )
        write_success(f"IAM role '{IAM_ROLE_NAME}' created")
    return IAM_ROLE_NAME


def create_and_attach_policy():
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{BUCKET_NAME}",
                    f"arn:aws:s3:::{BUCKET_NAME}/*",
                ],
            }
        ],
    }

    account_id = boto3.client("sts", region_name=AWS_REGION).get_caller_identity()["Account"]
    policy_arn = f"arn:aws:iam::{account_id}:policy/{IAM_POLICY_NAME}"

    try:
        iam.get_policy(PolicyArn=policy_arn)
        write_warn(f"IAM policy '{IAM_POLICY_NAME}' already exists, reusing it.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        response = iam.create_policy(
            PolicyName=IAM_POLICY_NAME,
            PolicyDocument=json.dumps(bucket_policy),
            Description="Least-privilege read-only access to the VolunteerConnect bucket",
        )
        policy_arn = response["Policy"]["Arn"]
        write_success(f"IAM policy '{IAM_POLICY_NAME}' created")

    iam.attach_role_policy(RoleName=IAM_ROLE_NAME, PolicyArn=policy_arn)
    write_success(f"Policy attached to role '{IAM_ROLE_NAME}'")
    return policy_arn


def create_instance_profile():
    try:
        iam.get_instance_profile(InstanceProfileName=INSTANCE_PROFILE_NAME)
        write_warn(f"Instance profile '{INSTANCE_PROFILE_NAME}' already exists, reusing it.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
        iam.create_instance_profile(InstanceProfileName=INSTANCE_PROFILE_NAME)
        write_success(f"Instance profile '{INSTANCE_PROFILE_NAME}' created")
        # IAM is eventually consistent - give it a moment before attaching a role
        time.sleep(8)

    profile = iam.get_instance_profile(InstanceProfileName=INSTANCE_PROFILE_NAME)
    existing_roles = [r["RoleName"] for r in profile["InstanceProfile"]["Roles"]]

    if IAM_ROLE_NAME not in existing_roles:
        iam.add_role_to_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME, RoleName=IAM_ROLE_NAME
        )
        write_success(f"Role '{IAM_ROLE_NAME}' added to instance profile")
        # propagation delay before EC2 can use it
        time.sleep(10)

    return INSTANCE_PROFILE_NAME


def setup_iam():
    """Orchestrator: run all IAM steps in order, return the instance profile name."""
    try:
        create_role()
        create_and_attach_policy()
        return create_instance_profile()
    except ClientError as e:
        write_error(f"IAM setup failed: {e}")
        raise
