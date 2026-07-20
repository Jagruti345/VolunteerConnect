"""
EC2 automation.
Launches an Ubuntu instance with the IAM instance profile, security group,
key pair, and a UserData bootstrap script that installs Apache + AWS CLI
and pulls the website from S3 automatically. Idempotent: if a running
instance already carries the project tag, it's reused instead of duplicated.
"""

import time
import boto3
from botocore.exceptions import ClientError

from config import (
    AWS_REGION,
    AMI_ID,
    INSTANCE_TYPE,
    KEY_NAME,
    EC2_TAG_NAME,
    BUCKET_NAME,
    ADMIN_PASSWORD,
    SECRET_KEY,
)
from modules.logger import write_success, write_warn, write_error

ec2_resource = boto3.resource("ec2", region_name=AWS_REGION)
ec2_client = boto3.client("ec2", region_name=AWS_REGION)


def _render_userdata():
    with open("userdata/userdata.sh") as f:
        script = f.read()
    script = script.replace("__BUCKET_NAME__", BUCKET_NAME)
    script = script.replace("__AWS_REGION__", AWS_REGION)
    script = script.replace("__ADMIN_PASSWORD__", ADMIN_PASSWORD)
    script = script.replace("__SECRET_KEY__", SECRET_KEY)
    return script


def get_existing_instance():
    response = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [EC2_TAG_NAME]},
            {"Name": "instance-state-name", "Values": ["pending", "running"]},
        ]
    )
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            return instance["InstanceId"]
    return None


def launch_instance(security_group_id, instance_profile_name):
    existing_id = get_existing_instance()
    if existing_id:
        write_warn(f"EC2 instance '{EC2_TAG_NAME}' already running ({existing_id}), reusing it.")
        return existing_id

    try:
        instances = ec2_resource.create_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            KeyName=KEY_NAME,
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[security_group_id],
            IamInstanceProfile={"Name": instance_profile_name},
            UserData=_render_userdata(),
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": EC2_TAG_NAME}],
                }
            ],
        )
        instance = instances[0]
        write_success(f"EC2 instance launch requested ({instance.id})")
        return instance.id
    except ClientError as e:
        write_error(f"EC2 launch failed: {e}")
        raise


def wait_for_running_and_ok(instance_id):
    instance = ec2_resource.Instance(instance_id)

    write_warn("Waiting for instance state 'running'...")
    instance.wait_until_running()
    instance.reload()
    write_success(f"Instance is running. Public IP: {instance.public_ip_address}")

    write_warn("Waiting for EC2 status checks to pass (this can take 1-2 minutes)...")
    waiter = ec2_client.get_waiter("instance_status_ok")
    waiter.wait(InstanceIds=[instance_id])
    write_success("Instance status checks passed")

    return instance.public_ip_address


def get_instance_id_by_tag():
    return get_existing_instance()
