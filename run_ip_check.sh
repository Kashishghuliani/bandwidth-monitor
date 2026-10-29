#!/bin/bash
set -e

PROJECT_DIR="/home/asus/projects/bandwidth-monitor"

cd "$PROJECT_DIR"

set -a
source "$PROJECT_DIR/.env.cron"
set +a

"$PROJECT_DIR/.venv/bin/python" manage.py check_target_ips
