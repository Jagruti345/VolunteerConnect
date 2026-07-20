"""
Phase 4 - CloudWatch monitoring.
Creates a CPU utilization alarm on the web server that notifies the SNS
topic if the instance is overloaded - basic ops monitoring with zero
manual console clicks.
"""

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, ALARM_NAME
from modules.logger import write_success, write_error

cloudwatch = boto3.client("cloudwatch", region_name=AWS_REGION)


def create_cpu_alarm(instance_id, sns_topic_arn):
    try:
        cloudwatch.put_metric_alarm(
            AlarmName=ALARM_NAME,
            ComparisonOperator="GreaterThanThreshold",
            EvaluationPeriods=2,
            MetricName="CPUUtilization",
            Namespace="AWS/EC2",
            Period=300,
            Statistic="Average",
            Threshold=80.0,
            ActionsEnabled=True,
            AlarmActions=[sns_topic_arn] if sns_topic_arn else [],
            AlarmDescription="Alerts when VolunteerConnect EC2 CPU exceeds 80% for 10 minutes",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        )
        write_success(f"CloudWatch CPU alarm '{ALARM_NAME}' created for {instance_id}")
    except ClientError as e:
        write_error(f"CloudWatch alarm creation failed: {e}")
