#!/bin/bash
set -euo pipefail
cd /opt/cloudtier
dnf install -y python3.11 python3.11-pip nginx amazon-cloudwatch-agent
id cloudtier >/dev/null 2>&1 || useradd --system --home-dir /opt/cloudtier cloudtier
mkdir -p /var/lib/cloudtier/files /var/lib/cloudtier/model /var/lib/cloudtier/backups
python3.11 -m venv /opt/cloudtier/venv
venv/bin/pip install --upgrade pip
venv/bin/pip install 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cpu
venv/bin/pip install -r aws/requirements-cloud.txt
set -a
source /etc/cloudtier.env
set +a
venv/bin/python src/ml_model/mri_inference.py --download --smoke-test
chown -R cloudtier:cloudtier /var/lib/cloudtier
cat > /etc/systemd/system/cloudtier.service <<'UNIT'
[Unit]
Description=CloudTier study archive API and MRI worker
After=network-online.target
Wants=network-online.target
[Service]
User=cloudtier
Group=cloudtier
WorkingDirectory=/opt/cloudtier/src/backend
EnvironmentFile=/etc/cloudtier.env
ExecStart=/opt/cloudtier/venv/bin/gunicorn 'cloud_app:create_app()' --bind 127.0.0.1:5000 --workers 1 --threads 8 --timeout 180 --access-logfile - --error-logfile -
Restart=always
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/cloudtier
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/nginx/nginx.conf <<'NGINX'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 512m;
    location / {
      proxy_pass http://127.0.0.1:5000;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_read_timeout 180s;
      proxy_request_buffering off;
    }
  }
}
NGINX
cat > /etc/systemd/system/cloudtier-backup.service <<'UNIT'
[Unit]
Description=Online backup of the study catalog and working data
[Service]
Type=oneshot
User=cloudtier
EnvironmentFile=/etc/cloudtier.env
WorkingDirectory=/opt/cloudtier
ExecStart=/opt/cloudtier/venv/bin/python aws/backup.py
UNIT
cat > /etc/systemd/system/cloudtier-backup.timer <<'UNIT'
[Unit]
Description=Daily archive pilot backup
[Timer]
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
UNIT
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'JSON'
{"logs":{"logs_collected":{"files":{"collect_list":[{"file_path":"/var/log/cloud-init-output.log","log_group_name":"/cloudtier-v2/bootstrap","log_stream_name":"{instance_id}"},{"file_path":"/var/log/nginx/error.log","log_group_name":"/cloudtier-v2/nginx","log_stream_name":"{instance_id}"}]}}}}
JSON
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
systemctl daemon-reload
nginx -t
systemctl enable --now cloudtier nginx cloudtier-backup.timer
curl --fail --retry 15 --retry-delay 2 --retry-all-errors http://127.0.0.1/api/health
