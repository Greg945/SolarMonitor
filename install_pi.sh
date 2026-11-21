#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/solar-monitor.service"

if [[ "$(id -u)" -eq 0 ]]; then
    echo "Bitte ohne sudo starten: bash install_pi.sh" >&2
    exit 1
fi

case "$PROJECT_DIR" in
    *" "*)
        echo "Der Projektpfad darf keine Leerzeichen enthalten: $PROJECT_DIR" >&2
        exit 1
        ;;
esac

if [[ ! -f "$PROJECT_DIR/app.py" || ! -f "$PROJECT_DIR/requirements.txt" ]]; then
    echo "install_pi.sh muss im SolarMonitor-Projektordner liegen." >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1 || ! command -v systemctl >/dev/null 2>&1; then
    echo "Dieses Installationsskript benötigt Raspberry Pi OS/Debian mit systemd." >&2
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    echo "SolarMonitor benötigt Python 3.11 oder neuer (aktuelles Raspberry Pi OS)." >&2
    exit 1
fi

echo "Installiere Python-Voraussetzungen..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

echo "Erstelle virtuelle Umgebung und installiere Pakete..."
python3 -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
sha256sum "$PROJECT_DIR/requirements.txt" | awk '{print $1}' > "$PROJECT_DIR/.requirements.sha256"

SERVICE_USER="$(id -un)"
sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=SolarMonitor Dashboard
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/bash $PROJECT_DIR/update_pi.sh
ExecStart=$PROJECT_DIR/.venv/bin/streamlit run $PROJECT_DIR/app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now solar-monitor.service

PI_ADDRESS="$(hostname -I | awk '{print $1}')"
echo
echo "SolarMonitor ist installiert und startet automatisch beim Booten."
echo "Dashboard: http://${PI_ADDRESS:-<pi-ip>}:8501"
echo "Status:     sudo systemctl status solar-monitor"
echo "Logs:       sudo journalctl -u solar-monitor -f"
