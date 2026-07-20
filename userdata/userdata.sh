#!/bin/bash
# VolunteerConnect bootstrap script.
# Runs automatically on first EC2 boot (passed in as EC2 UserData).
# Placeholders below are substituted by modules/ec2.py before this is sent
# to AWS - no manual editing needed.

set -e

apt-get update -y
apt-get install -y python3 python3-pip python3-venv unzip curl

# Install AWS CLI v2 if not already present
if ! command -v aws &> /dev/null; then
    cd /tmp
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -oq awscliv2.zip
    ./aws/install
fi

BUCKET_NAME="__BUCKET_NAME__"
AWS_REGION="__AWS_REGION__"
ADMIN_PASSWORD="__ADMIN_PASSWORD__"
SECRET_KEY="__SECRET_KEY__"

mkdir -p /opt/volunteerconnect

# Pull the latest app code from S3 - never touch the local SQLite data
# directory, so redeploys don't wipe registrations.
aws s3 sync "s3://$BUCKET_NAME" /opt/volunteerconnect --region "$AWS_REGION" --delete --exclude "data/*"

cd /opt/volunteerconnect

# Use a dedicated virtual environment - far more reliable across Ubuntu/pip
# versions than fighting PEP 668's externally-managed-environment guard.
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

cat > /etc/systemd/system/volunteerconnect.service << SERVICE
[Unit]
Description=VolunteerConnect Flask App
After=network.target

[Service]
WorkingDirectory=/opt/volunteerconnect
Environment="ADMIN_PASSWORD=$ADMIN_PASSWORD"
Environment="SECRET_KEY=$SECRET_KEY"
ExecStart=/opt/volunteerconnect/venv/bin/gunicorn -w 3 -b 0.0.0.0:80 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable volunteerconnect
systemctl restart volunteerconnect

echo "VolunteerConnect deployment complete" > /var/log/volunteerconnect-deploy.log
