#!/bin/sh
# Root-owned, fixed command used by the optional MQTT monitor. Checks only.
set -eu
exec 9>/run/lock/xsm-player-update-check.lock
flock -n 9 || exit 0
apt-get update
apt-cache policy xiboplayer-chromium
apt list --upgradable
