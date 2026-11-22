#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
    echo "Bitte ohne sudo starten: bash setup_tailscale.sh" >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1 || ! command -v systemctl >/dev/null 2>&1; then
    echo "Dieses Skript benötigt Raspberry Pi OS/Debian mit systemd." >&2
    exit 1
fi

if ! command -v tailscale >/dev/null 2>&1; then
    if ! command -v curl >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y curl
    fi

    echo "Installiere Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

SYSCTL_FILE="/etc/sysctl.d/99-tailscale-exit-node.conf"
sudo tee "$SYSCTL_FILE" >/dev/null <<'EOF'
# Allow Tailscale to forward traffic for exit-node clients.
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
sudo sysctl -p "$SYSCTL_FILE" >/dev/null

sudo systemctl enable --now tailscaled.service

echo
echo "Melde den Raspberry Pi bei deinem Tailscale-Konto an."
echo "Falls noch keine Anmeldung besteht, zeigt Tailscale jetzt einen Login-Link an."
sudo tailscale up --advertise-exit-node

echo
echo "Tailscale ist eingerichtet und startet automatisch beim Booten."
echo "Nach der Anmeldung musst du den Pi einmal in der Tailscale-Admin-Konsole als Exit-Node freigeben."
