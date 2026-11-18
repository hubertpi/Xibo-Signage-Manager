#!/usr/bin/env bash
# Add MQTT monitoring to an already configured Xibo Pi without touching playback.
set -euo pipefail
umask 022
if [[ ${1:-} == --help ]]; then
    echo 'Usage: install-mqtt.sh'
    echo 'Run as the existing Xibo desktop user. Prompts for MQTT broker settings.'
    exit 0
fi
[[ $# == 0 ]] || { echo 'Unknown argument' >&2; exit 2; }
if [[ $(id -u) == 0 ]]; then
    echo 'Run as the normal Xibo desktop user, without sudo.' >&2
    exit 1
fi
desktop_user=$(id -un)
desktop_uid=$(id -u)
[[ "$desktop_user" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo 'Unsupported account name' >&2; exit 1; }
if [[ "$HOME" =~ [[:space:]\"\\%] ]]; then
    echo 'Home paths containing whitespace, quotes, backslashes or % are unsupported.' >&2
    exit 1
fi
[[ -f "$HOME/.config/systemd/user/xiboplayer-chromium.service" ]] || {
    echo 'Run as the desktop account that owns the existing Xibo player service.' >&2
    exit 1
}
for name in player-start.sh player-stop.sh player-restart.sh check-updates.sh check-updates-user.sh; do
    helper="/opt/xsm-player/$name"
    [[ -x "$helper" && ! -L "$helper" && $(stat -c %u "$helper") == 0 ]] || {
        echo "Required root-owned player helper is missing: $helper" >&2
        exit 1
    }
    mode=$(stat -c %a "$helper")
    (( (8#$mode & 022) == 0 )) || { echo "Unsafe player helper permissions: $helper" >&2; exit 1; }
done
sudo -v
sudo apt-get update
sudo apt-get install -y ca-certificates git python3 python3-venv python3-dev gcc
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
staging=''
cleanup() { if [[ -n "$staging" ]]; then rm -rf -- "$staging"; fi; }
trap cleanup EXIT
if [[ ! -f "$source_dir/configure.py" ]]; then
    staging=$(mktemp -d)
    git init -q "$staging/repo"
    git -C "$staging/repo" remote add origin https://github.com/hubertpi/Xibo-Signage-Manager.git
    git -C "$staging/repo" fetch --depth=1 origin "${XSM_INSTALL_REF:-main}"
    git -C "$staging/repo" checkout -q --detach FETCH_HEAD
    source_dir="$staging/repo/player"
fi
# Import just the monitor configurator: don't write player settings or restart it.
python3 -c 'import sys, getpass; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from configure import configure_monitor; configure_monitor(Path.home(), getpass.getuser())' "$source_dir" </dev/tty
monitor_root="$HOME/.local/share/xsm-player/rpi-mqtt-monitor"
# Use only the fixed root-owned helpers and reboot operation used by the controls.
sudoers=$(mktemp)
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl reboot -i, /usr/bin/apt update, /opt/xsm-player/check-updates.sh\n' "$desktop_user" > "$sudoers"
if ! sudo visudo -cf "$sudoers"; then
    rm -f "$sudoers"
    exit 1
fi
sudo install -m 0440 "$sudoers" /etc/sudoers.d/xsm-player-monitor
rm -f "$sudoers"
service=$(mktemp)
cat > "$service" <<EOF
[Unit]
Description=Raspberry Pi MQTT Monitor for Xibo
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$desktop_user
Environment=XDG_RUNTIME_DIR=/run/user/$desktop_uid
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$desktop_uid/bus
WorkingDirectory=$monitor_root
ExecStart=$monitor_root/rpi_mon_env/bin/python $monitor_root/src/rpi-cpu2mqtt.py --service
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo install -m 0644 "$service" /etc/systemd/system/xsm-rpi-mqtt-monitor.service
rm -f "$service"
sudo systemctl daemon-reload
sudo systemctl enable xsm-rpi-mqtt-monitor.service
sudo systemctl restart xsm-rpi-mqtt-monitor.service
sudo systemctl --no-pager --full status xsm-rpi-mqtt-monitor.service
printf '%s\n' 'MQTT monitor installed. Xibo playback and registration were left unchanged.'
printf '%s\n' 'HA device discovery follows when the configured MQTT broker is reachable.'
