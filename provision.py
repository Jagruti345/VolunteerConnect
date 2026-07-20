"""
VolunteerConnect - one-command AWS provisioning and deployment.

    python provision.py

does everything: IAM role/policy/instance profile, security group, key pair,
S3 bucket + website upload, EC2 launch, Apache install, website deployment,
live-site verification, and (optionally) SNS/SES/CloudWatch monitoring.

Safe to run more than once - every module checks for existing resources
before creating new ones.
"""

import sys

from config import ENABLE_PHASE4, SES_SENDER_EMAIL, SES_RECIPIENT_EMAIL
from modules.logger import write_log, write_success, write_error
from modules import iam, security_group, keypair, s3, ec2, deploy

if ENABLE_PHASE4:
    from modules import sns, ses, cloudwatch


def main():
    write_log("========== VolunteerConnect Deployment Started ==========")

    try:
        # ---------- Phase 1: Infrastructure ----------
        instance_profile_name = iam.setup_iam()
        security_group_id = security_group.create_security_group()
        keypair.create_key_pair()
        s3.create_bucket()
        s3.upload_website()

        instance_id = ec2.launch_instance(security_group_id, instance_profile_name)
        public_ip = ec2.wait_for_running_and_ok(instance_id)

        # ---------- Deployment verification ----------
        deployed_ok = deploy.verify_deployment(public_ip)

        # ---------- Phase 4: Advanced AWS (optional) ----------
        topic_arn = None
        if ENABLE_PHASE4:
            write_log("---------- Phase 4: Notifications & Monitoring ----------")
            topic_arn = sns.create_topic()
            sns.subscribe_email(topic_arn, SES_RECIPIENT_EMAIL)
            cloudwatch.create_cpu_alarm(instance_id, topic_arn)

            ses.verify_email_identity(SES_SENDER_EMAIL)
            ses.verify_email_identity(SES_RECIPIENT_EMAIL)
            if deployed_ok:
                ses.send_deployment_email(public_ip)

            status = "SUCCESS" if deployed_ok else "COMPLETED WITH WARNINGS"
            sns.publish_message(
                topic_arn,
                f"VolunteerConnect deployment: {status}",
                f"Website: http://{public_ip}\nInstance: {instance_id}",
            )

        # ---------- Summary ----------
        write_log("========== Deployment Summary ==========")
        write_success(f"Instance ID : {instance_id}")
        write_success(f"Public IP   : {public_ip}")
        write_success(f"Website URL : http://{public_ip}")
        if not deployed_ok:
            write_error("Site was not verified reachable yet - see notes above.")

        write_log("========== VolunteerConnect Deployment Finished ==========")

    except Exception as e:
        write_error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
