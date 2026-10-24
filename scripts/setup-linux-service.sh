#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVICE_NAME="${SERVICE_NAME:-$(basename "$APP_DIR" | tr '[:upper:]' '[:lower:]')}"
APP_USER="${APP_USER:-$(id -un)}"
APP_GROUP="${APP_GROUP:-$(id -gn)}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8017}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd is required for this script." >&2
  exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required for service installation." >&2
  exit 1
fi

mkdir -p "$APP_DIR/storage" "$APP_DIR/scripts"

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

if [ ! -f "$ENV_FILE" ] && [ -f "$APP_DIR/.env.example" ]; then
  cp "$APP_DIR/.env.example" "$ENV_FILE"
fi

cd "$APP_DIR"
# Recognize only complete historical schemas, then apply every pending migration.
# Unknown/partial schemas stop here before the service is installed or restarted.
"$VENV_DIR/bin/python" -m scripts.migrate_database

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=IdeaDock service
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_DIR
EnvironmentFile=-$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=AUTO_BOOTSTRAP_DB=false
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host $APP_HOST --port $APP_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo
echo "Service installed and started:"
echo "  sudo systemctl status $SERVICE_NAME --no-pager"
echo "  sudo journalctl -u $SERVICE_NAME -n 100 --no-pager"
echo "  http://$(hostname -I | awk '{print $1}'):${APP_PORT}"
