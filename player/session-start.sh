#!/bin/sh
set -eu
: "${DISPLAY:?Run this from the X11 desktop session}"
systemctl --user import-environment DISPLAY
if [ -n "${XAUTHORITY:-}" ]; then
    systemctl --user import-environment XAUTHORITY
else
    systemctl --user unset-environment XAUTHORITY
fi
systemctl --user reset-failed xiboplayer-chromium.service || true
systemctl --user start xsm-player-watchdog.timer
if [ -e "$HOME/.local/state/xsm-player/paused" ]; then
    exit 0
fi
exec systemctl --user start xiboplayer-chromium.service
