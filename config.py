"""
Central configuration for VolunteerConnect AWS automation.
All modules import from here. Nothing here should require manual editing
after .env is filled in.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------- Core ----------------
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
PROJECT_NAME = "VolunteerConnect"

# ---------------- EC2 ----------------
AMI_ID = os.getenv("AMI_ID", "ami-0f918f7e67a3323f0")  # Ubuntu 22.04 LTS, ap-south-1
INSTANCE_TYPE = os.getenv("INSTANCE_TYPE", "t3.micro")
KEY_NAME = "VolunteerConnect-key"
KEY_FILE = f"{KEY_NAME}.pem"
EC2_TAG_NAME = "VolunteerConnect-Server"

# ---------------- S3 ----------------
BUCKET_NAME = os.getenv("BUCKET_NAME", "volunteerconnect-static-site-2026")
APP_DIR = "webapp"
APP_EXCLUDE_PREFIXES = ("data/", "__pycache__/")

# ---------------- Web app secrets (passed to EC2 as env vars) ----------------
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")
SECRET_KEY = os.getenv("SECRET_KEY", "please-change-this-secret-key")

# ---------------- Security Group ----------------
SECURITY_GROUP_NAME = "VolunteerConnect-SG"
SECURITY_GROUP_DESC = "Security group for VolunteerConnect web server (HTTP + SSH)"

# ---------------- IAM ----------------
IAM_ROLE_NAME = "VolunteerConnect-EC2-Role"
IAM_POLICY_NAME = "VolunteerConnect-S3-ReadOnly-Policy"
INSTANCE_PROFILE_NAME = "VolunteerConnect-Profile"

# ---------------- Logging ----------------
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "deployment.log")

# ---------------- Phase 4 (optional advanced AWS) ----------------
ENABLE_PHASE4 = os.getenv("ENABLE_PHASE4", "false").lower() == "true"

SNS_TOPIC_NAME = "VolunteerConnect-Alerts"
ALARM_NAME = "VolunteerConnect-High-CPU-Alarm"

SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "")
SES_RECIPIENT_EMAIL = os.getenv("SES_RECIPIENT_EMAIL", "")
