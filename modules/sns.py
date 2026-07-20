"""
Phase 4 - SNS notifications.
Creates an SNS topic for deployment/ops alerts and publishes a message
whenever provision.py finishes (success or failure). Optional - controlled
by ENABLE_PHASE4 in .env.
"""

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, SNS_TOPIC_NAME, SES_RECIPIENT_EMAIL
from modules.logger import write_success, write_warn, write_error

sns = boto3.client("sns", region_name=AWS_REGION)


def create_topic():
    try:
        response = sns.create_topic(Name=SNS_TOPIC_NAME)
        topic_arn = response["TopicArn"]
        write_success(f"SNS topic ready: {topic_arn}")
        return topic_arn
    except ClientError as e:
        write_error(f"SNS topic creation failed: {e}")
        raise


def subscribe_email(topic_arn, email):
    if not email:
        write_warn("No recipient email configured, skipping SNS email subscription.")
        return None
    try:
        subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn)["Subscriptions"]
        if any(s["Endpoint"] == email for s in subs):
            write_warn(f"'{email}' is already subscribed to SNS topic.")
            return None

        sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
        write_success(f"Subscription request sent to '{email}' - confirm it via the email AWS sends.")
    except ClientError as e:
        write_error(f"SNS subscription failed: {e}")
        raise


def publish_message(topic_arn, subject, message):
    try:
        sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        write_success("SNS notification published")
    except ClientError as e:
        write_error(f"SNS publish failed: {e}")
