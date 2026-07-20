"""
Security group automation.
Opens only what the app needs: SSH (22) for admin access and HTTP (80)
for the public website. Idempotent - reuses the group if it already exists.
"""

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, SECURITY_GROUP_NAME, SECURITY_GROUP_DESC
from modules.logger import write_success, write_warn, write_error

ec2 = boto3.client("ec2", region_name=AWS_REGION)


def get_default_vpc_id():
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
    if not vpcs["Vpcs"]:
        raise RuntimeError("No default VPC found in this region/account.")
    return vpcs["Vpcs"][0]["VpcId"]


def get_existing_group_id():
    result = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [SECURITY_GROUP_NAME]}]
    )
    if result["SecurityGroups"]:
        return result["SecurityGroups"][0]["GroupId"]
    return None


def create_security_group():
    try:
        existing_id = get_existing_group_id()
        if existing_id:
            write_warn(f"Security group '{SECURITY_GROUP_NAME}' already exists, reusing it.")
            return existing_id

        vpc_id = get_default_vpc_id()
        response = ec2.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description=SECURITY_GROUP_DESC,
            VpcId=vpc_id,
        )
        group_id = response["GroupId"]

        ec2.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP"}],
                },
            ],
        )
        write_success(f"Security group '{SECURITY_GROUP_NAME}' created ({group_id})")
        return group_id
    except ClientError as e:
        write_error(f"Security group setup failed: {e}")
        raise
