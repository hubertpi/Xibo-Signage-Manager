#!/usr/bin/env bash
# Run as the desktop user, not root. Safe to rerun on the existing test Pi.
set -euo pipefail
umask 022

configure=0
mqtt=0
autologin=1
timezone=America/Chicago
for arg in "$@"; do
    case "$arg" in
        --configure) configure=1 ;;
        --mqtt) mqtt=1 ;;
        --no-autologin) autologin=0 ;;
        --timezone=*) timezone=${arg#*=} ;;
        --help)
            echo 'Usage: install.sh [--configure] [--mqtt] [--no-autologin] [--timezone=America/Chicago]'
            echo 'Requires Raspberry Pi OS 13 Desktop. Configures X11, login startup, cursor hiding and watchdog.'
            exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done
if [[ $(id -u) == 0 ]]; then
    echo 'Run as your normal desktop user; this installer uses sudo where needed.' >&2
    exit 1
fi
desktop_user=$(id -un)
desktop_uid=$(id -u)
if [[ ! "$desktop_user" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
    echo 'Unsupported account name' >&2; exit 1
fi
if [[ "$HOME" =~ [[:space:]\"\\%] ]]; then
    echo 'Home paths containing whitespace, quotes, backslashes or % are unsupported.' >&2; exit 1
fi
source /etc/os-release
if [[ ${VERSION_CODENAME:-} != trixie || ! -e /usr/bin/raspi-config || ! -d /etc/lightdm ]]; then
    echo 'This recipe requires Raspberry Pi OS 13 (Trixie) Desktop with LightDM and raspi-config.' >&2
    exit 1
fi
case "$(dpkg --print-architecture)" in armhf|arm64) ;; *) echo 'Requires armhf or arm64 Raspberry Pi OS' >&2; exit 1 ;; esac
sudo -v

sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3 nodejs jq chromium unclutter-xfixes python3-websocket
if (( mqtt )); then
    sudo apt-get install -y python3-venv python3-dev gcc
fi

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
staging=''
cleanup() { if [[ -n "$staging" ]]; then rm -rf -- "$staging"; fi; }
trap cleanup EXIT
if [[ ! -f "$source_dir/configure.py" || ! -f "$source_dir/watchdog.py" ]]; then
    staging=$(mktemp -d)
    git init -q "$staging/repo"
    git -C "$staging/repo" remote add origin https://github.com/hubertpi/Xibo-Signage-Manager.git
    git -C "$staging/repo" fetch --depth=1 origin "${XSM_INSTALL_REF:-main}"
    git -C "$staging/repo" checkout -q --detach FETCH_HEAD
    source_dir="$staging/repo/player"
fi
sudo install -d -m 0755 /etc/apt/keyrings
key_file=$(mktemp)
curl -fsSL https://dl.xiboplayer.org/deb/DEB-GPG-KEY-xiboplayer -o "$key_file"
sudo install -m 0644 "$key_file" /etc/apt/keyrings/xiboplayer.asc
rm -f "$key_file"
echo 'deb [signed-by=/etc/apt/keyrings/xiboplayer.asc] https://dl.xiboplayer.org/deb/debian/trixie ./' |
    sudo tee /etc/apt/sources.list.d/xiboplayer.list >/dev/null
sudo apt-get update
player_version=0.7.22-1
installed=$(dpkg-query -W -f='${Version}' xiboplayer-chromium 2>/dev/null || true)
if [[ -n "$installed" && "$installed" != "$player_version" ]]; then
    echo "Existing player $installed differs from validated $player_version; left untouched." >&2
    exit 1
fi

systemctl --user stop xsm-player-watchdog.timer 2>/dev/null || true
systemctl --user stop xiboplayer-chromium.service 2>/dev/null || true
sudo apt-get install -y "xiboplayer-chromium=$player_version"
sudo install -d -m 0755 /opt/xsm-player
for name in patch_player.py configure.py watchdog.py session-start.sh control.sh \
            player-start.sh player-stop.sh player-restart.sh check-updates.sh check-updates-user.sh; do
    sudo install -m 0755 "$source_dir/$name" "/opt/xsm-player/$name"
done
sudo ln -sfn /opt/xsm-player/control.sh /usr/local/bin/xsm-player
sudo python3 /opt/xsm-player/patch_player.py
# The setup fix is tied to this release; an unattended package replacement
# would discard it. OS packages remain unaffected.
sudo apt-mark hold xiboplayer-chromium

config_args=()
(( configure )) && config_args+=(--configure)
(( mqtt )) && config_args+=(--mqtt)
if (( configure || mqtt )); then
    # Real terminal, even when this script was fetched with process substitution.
    python3 /opt/xsm-player/configure.py "${config_args[@]}" </dev/tty
else
    python3 /opt/xsm-player/configure.py
fi

mkdir -p "$HOME/.config/systemd/user" "$HOME/.config/autostart" "$HOME/.local/share/applications"
# Replace the target-only enablement used during the live session with the
# desktop hook. The unit itself still provides restart and journal handling.
systemctl --user disable xiboplayer-chromium.service 2>/dev/null || true
for name in xiboplayer-chromium.service xsm-player-watchdog.service xsm-player-watchdog.timer; do
    install -m 0644 "$source_dir/$name" "$HOME/.config/systemd/user/$name"
done
legacy="$HOME/.config/systemd/user/xiboplayer-chromium.service.d/display.conf"
if [[ -f "$legacy" ]] && [[ $(tr -d '[:space:]' < "$legacy") == '[Service]Environment=DISPLAY=:0' ]]; then
    rm -f "$legacy"
fi
cat > "$HOME/.config/autostart/xsm-player.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Xibo Player
Exec=/opt/xsm-player/session-start.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
for action in start stop; do
    cat > "$HOME/.local/share/applications/xsm-player-$action.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Xibo Player $action
Exec=/opt/xsm-player/control.sh $action
Terminal=false
Categories=Utility;
EOF
done

sudo timedatectl set-timezone "$timezone"
# Use the X11 path actually validated with this CMS/player. Preserve backups of
# the display-manager configuration before selecting the desktop session.
if [[ ! -f /etc/lightdm/lightdm.conf.before-xsm-player ]]; then
    sudo cp -a /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.before-xsm-player
fi
sudo raspi-config nonint do_wayland W1
if (( autologin )); then
    sudo raspi-config nonint do_boot_behaviour B4
fi

if (( mqtt )); then
    monitor_root="$HOME/.local/share/xsm-player/rpi-mqtt-monitor"
    # Run the established monitor as the desktop user. Grant only the exact
    # privileged operations used by its enabled controls, not arbitrary scripts.
    sudoers=$(mktemp)
    cat > "$sudoers" <<EOF
$desktop_user ALL=(root) NOPASSWD: /usr/bin/systemctl reboot -i, /usr/bin/apt update, /opt/xsm-player/check-updates.sh
EOF
    sudo visudo -cf "$sudoers"
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
    sudo systemctl enable --now xsm-rpi-mqtt-monitor.service
fi

systemctl --user daemon-reload
systemctl --user reset-failed xiboplayer-chromium.service || true
echo 'Installation complete. Existing CMS identity and credentials were preserved.'
echo 'The validated player package is held; update checks do not install upgrades.'
echo 'Start: xsm-player start    Stop intentionally: xsm-player stop'
echo 'Restart: xsm-player restart    Logs: journalctl --user -u xiboplayer-chromium -n 60'
echo 'Reboot to verify X11 desktop auto-login, player startup, cursor hiding and watchdog.'
echo 'CMS: authorize this display, assign the bulletin layout, and set download window 00:00–23:59.'
