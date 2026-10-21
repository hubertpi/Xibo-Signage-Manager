#!/bin/sh
set -eu
state_dir="$HOME/.local/state/xsm-player"
mkdir -p "$state_dir"
case "${1:-status}" in
    stop)
        touch "$state_dir/paused"
        systemctl --user stop xiboplayer-chromium.service
        ;;
    start|restart)
        rm -f "$state_dir/paused" "$state_dir/watchdog.json"
        systemctl --user reset-failed xiboplayer-chromium.service || true
        systemctl --user start xsm-player-watchdog.timer
        systemctl --user "$1" xiboplayer-chromium.service
        ;;
    status)
        systemctl --user status xiboplayer-chromium.service --no-pager
        ;;
    *) echo 'Usage: xsm-player start|stop|restart|status' >&2; exit 2 ;;
esac
