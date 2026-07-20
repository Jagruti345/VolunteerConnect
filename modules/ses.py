"""
Phase 4 - SES email.
Sends a deployment confirmation email with the live site URL. Note: a new
AWS account's SES is in sandbox mode, meaning BOTH the sender and recipient
addresses must be verified in the SES console before this will send. This
one-time verification is an AWS account restriction, not something
automatable away - everything else here is fully automatic.
"""

import boto3
from botocore.exceptions import ClientError

from config import AWS_REGION, SES_SENDER_EMAIL, SES_RECIPIENT_EMAIL
from modules.logger import write_success, write_warn, write_error

ses = boto3.client("ses", region_name=AWS_REGION)


def verify_email_identity(email):
    """Kicks off SES verification for an address (one-time, click link in inbox)."""
    if not email:
        return
    try:
        identities = ses.list_identities(IdentityType="EmailAddress")["Identities"]
        if email in identities:
            write_warn(f"'{email}' already registered as an SES identity.")
            return
        ses.verify_email_identity(EmailAddress=email)
        write_warn(f"Verification email sent to '{email}' - click the link in that email once.")
    except ClientError as e:
        write_error(f"SES identity verification failed: {e}")


def send_deployment_email(public_ip):
    if not SES_SENDER_EMAIL or not SES_RECIPIENT_EMAIL:
        write_warn("SES sender/recipient not configured, skipping deployment email.")
        return

    try:
        ses.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={"ToAddresses": [SES_RECIPIENT_EMAIL]},
            Message={
                "Subject": {"Data": "VolunteerConnect deployment complete"},
                "Body": {
                    "Text": {
                        "Data": f"Your VolunteerConnect site is live at http://{public_ip}"
                    }
                },
            },
        )
        write_success(f"Deployment confirmation email sent to '{SES_RECIPIENT_EMAIL}'")
    except ClientError as e:
        write_error(f"SES send failed: {e}")
