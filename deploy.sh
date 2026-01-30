#!/bin/bash
# Skrypt deploy wywoływany przez webhook (np. po pushu na GitHub).
# Uruchamia: git pull, opcjonalnie pip install, restart usługi systemd.
# Ustaw na VPS: chmod +x deploy.sh

set -e
APP_DIR="${DEPLOY_APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
cd "$APP_DIR"

echo "[deploy] $(date -Iseconds) Pulling..."
git pull

if [ -n "${DEPLOY_PIP:-}" ] || [ -f "requirements.txt" ]; then
    echo "[deploy] Installing dependencies..."
    if [ -d "venv" ]; then
        ./venv/bin/pip install -r requirements.txt -q
    elif command -v pip3 &>/dev/null; then
        pip3 install -r requirements.txt -q --user
    fi
fi

SERVICE="${DEPLOY_SERVICE:-metin2pricechart}"
if command -v systemctl &>/dev/null && systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
    echo "[deploy] Restarting $SERVICE..."
    systemctl restart "$SERVICE"
    echo "[deploy] Done."
else
    echo "[deploy] Service $SERVICE nie działa przez systemd - zrestartuj aplikację ręcznie (np. kill + uruchom ponownie)."
fi
