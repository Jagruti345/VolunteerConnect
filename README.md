# VolunteerConnect - Automated AWS Deployment

A real, working NGO & Volunteer collaboration platform (Flask + SQLite), deployed
end-to-end with one command.

- Anyone can browse events and register as a volunteer
- NGOs log in and post/edit/delete events
- NGOs see exactly who registered for each event, and can export the list as CSV
- Fully responsive, professional UI

## What runs automatically

```
python provision.py
```

does all of this, with zero manual AWS Console steps:

- Creates IAM role, least-privilege S3 policy, and instance profile
- Creates a security group (HTTP + SSH)
- Creates an EC2 key pair
- Creates a private S3 bucket and uploads `webapp/` (the Flask app)
- Launches an Ubuntu EC2 instance
- Bootstraps it via UserData: installs Python/Flask/Gunicorn, pulls the app from S3,
  runs it as a systemd service on port 80 (auto-restarts if it ever crashes)
- Polls the public IP until the site is actually live
- **(optional, Phase 4)** Creates an SNS topic + email subscription, a CloudWatch CPU alarm, and sends an SES deployment-confirmation email

Every step is idempotent — re-running `provision.py` reuses existing resources instead
of duplicating them, and redeploys never wipe your data (the SQLite database lives
outside the synced code path on the server).

## Try it locally first (no AWS needed)

```bash
cd webapp
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 — browse events, and visit http://localhost:5000/admin/login
(default password `changeme123` unless you set `ADMIN_PASSWORD`) to post an event and
see who registers for it.

## Setup (one time)

```bash
pip install -r requirements.txt
aws configure          # access key, secret key, region (ap-south-1), output=json
aws sts get-caller-identity   # sanity check
cp .env.example .env
```

Edit `.env` if you want to change region/bucket name, or turn on Phase 4:

```
ENABLE_PHASE4=true
SES_SENDER_EMAIL=you@example.com
SES_RECIPIENT_EMAIL=you@example.com
```

> Note: SES starts in sandbox mode on a new AWS account — both sender and recipient addresses must click a one-time verification link AWS emails them. That's an AWS account restriction, not something automation can skip.

## Run it

```bash
python provision.py
```

Output ends with something like:

```
[✓] Instance ID : i-0abc123...
[✓] Public IP   : 13.234.x.x
[✓] Website URL : http://13.234.x.x
```

Open that URL in a browser — the site is live.

## Project structure

```
VolunteerConnect-AWS/
├── webapp/                    # the actual application (uploaded to S3, run on EC2)
│   ├── app.py                 # Flask app: routes, DB, admin auth
│   ├── requirements.txt       # flask, gunicorn
│   ├── templates/             # Jinja2 HTML templates
│   ├── static/                # style.css, script.js
│   └── data/                  # SQLite DB lives here at runtime (not synced/deleted)
├── userdata/
│   └── userdata.sh       # EC2 bootstrap: Python/Flask/Gunicorn + systemd service
├── modules/
│   ├── iam.py
│   ├── security_group.py
│   ├── keypair.py
│   ├── s3.py
│   ├── ec2.py
│   ├── deploy.py         # live-site verification
│   ├── logger.py
│   ├── sns.py            # Phase 4
│   ├── ses.py             # Phase 4
│   └── cloudwatch.py     # Phase 4
├── logs/deployment.log
├── config.py
├── provision.py          # orchestrator — run this
├── requirements.txt
└── .env.example
```

## Tearing it down

There's no auto-teardown script bundled (deliberately — safer to review before deleting live infra), but the mirror-image commands are:

```bash
aws ec2 terminate-instances --instance-ids <id>
aws s3 rb s3://<bucket-name> --force
aws ec2 delete-key-pair --key-name VolunteerConnect-key
aws ec2 delete-security-group --group-id <sg-id>
aws iam remove-role-from-instance-profile --instance-profile-name VolunteerConnect-Profile --role-name VolunteerConnect-EC2-Role
aws iam delete-instance-profile --instance-profile-name VolunteerConnect-Profile
aws iam detach-role-policy --role-name VolunteerConnect-EC2-Role --policy-arn <policy-arn>
aws iam delete-role --role-name VolunteerConnect-EC2-Role
```

## Roadmap beyond this

- **Phase 2/3 (backend):** API Gateway + Lambda + DynamoDB to make volunteer registration and campaign posting dynamic instead of front-end-only.
- **Phase 5 (production):** custom domain + HTTPS via ACM, CloudFront CDN, CI/CD via GitHub Actions, Cognito auth.
