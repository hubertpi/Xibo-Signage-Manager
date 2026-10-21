#!/usr/bin/env python3
"""Configure the signed-in user's player and optional existing MQTT monitor."""
import argparse
import getpass
import json
import os
from pathlib import Path
import socket
import subprocess

MONITOR_REV = 'e641464d74b924b8b3e7fecf3a9580ba0b3554bc'


def player_config(previous, supplied=None):
    """Preserve registration, identity and existing credentials on repair."""
    result = dict(previous)
    if supplied:
        result.update(supplied)
    result.update(browser='chromium', kioskMode=True, fullscreen=True,
                  hideMouseCursor=True, preventSleep=True)
    # The launcher otherwise forces Chromium --v=1 on every launch.
    flags = result.get('extraBrowserFlags', '').split()
    flags = [f for f in flags if not f.startswith('--v=')]
    result['extraBrowserFlags'] = ' '.join(flags + ['--v=0'])
    return result


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(text)
    path.chmod(0o600)


def configure_player(home, configure=False):
    path = home / '.config/xiboplayer/chromium/config.json'
    previous = json.loads(path.read_text()) if path.exists() else {}
    supplied = None
    if configure:
        # getpass reads /dev/tty, so a pasted next command cannot be read as
        # configuration from this program's redirected stdin.
        url = input('CMS URL (blank: keep existing / configure on screen): ').strip()
        if url:
            if not url.startswith(('http://', 'https://')):
                raise ValueError('CMS URL must start with http:// or https://')
            key = getpass.getpass('CMS Secret Key (blank: configure on screen): ').strip()
            supplied = {'cmsUrl': url.rstrip('/')}
            if key:
                supplied['cmsKey'] = key
            supplied['displayName'] = input('Display name: ').strip() or socket.gethostname()
    write_private(path, json.dumps(player_config(previous, supplied), indent=2) + '\n')
    print('Player settings saved; existing browser registration retained')


def monitor_overrides(values, user):
    return dict(values, os_user=user, discovery_messages=True, retain=True,
                service_sleep_time=60, update_check_interval=3600,
                restart_button=True, shutdown_button=False,
                apt_updates=True, git_update=False, update=False,
                local_ipv4=True, rpi_power_status=True,
                display_control=False, use_availability=True,
                custom_scripts=[
                    ['/opt/xsm-player/player-start.sh', 'mdi:play', 'start_player'],
                    ['/opt/xsm-player/player-stop.sh', 'mdi:stop', 'stop_player'],
                    ['/opt/xsm-player/player-restart.sh', 'mdi:monitor', 'restart_player'],
                    ['/opt/xsm-player/check-updates-user.sh', 'mdi:update', 'check_updates'],
                ])


def configure_monitor(home, user):
    root = home / '.local/share/xsm-player/rpi-mqtt-monitor'
    config = root / 'src/config.py'
    if not root.exists():
        subprocess.run(['git', 'clone', 'https://github.com/hjelev/rpi-mqtt-monitor.git',
                        str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'checkout', '--detach', MONITOR_REV], check=True)
    else:
        revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != MONITOR_REV:
            raise ValueError('Existing monitor revision differs; left untouched')
    venv = root / 'rpi_mon_env'
    subprocess.run(['python3', '-m', 'venv', str(venv)], check=True)
    subprocess.run([str(venv / 'bin/pip'), 'install', '-r', str(root / 'requirements.txt')], check=True)
    if config.exists():
        print('Existing MQTT monitor configuration retained')
        return
    host = input('MQTT broker IP/hostname (reachable FROM the Pi): ').strip()
    if not host or host == 'core-mosquitto':
        raise ValueError('Use the LAN broker hostname/IP, not HA add-on name core-mosquitto')
    port = int(input('MQTT port [1883]: ').strip() or '1883')
    if not 1 <= port <= 65535:
        raise ValueError('Invalid MQTT port')
    username = input('MQTT username: ').strip()
    password = getpass.getpass('MQTT password: ')
    tls = input('Use MQTT TLS? [y/N]: ').strip().lower() == 'y'
    values = monitor_overrides({'mqtt_host': host, 'mqtt_port': str(port),
                                'mqtt_user': username, 'mqtt_password': password,
                                'mqtt_tls': tls}, user)
    example = (root / 'src/config.py.example').read_text()
    # repr handles quotes/backslashes in secrets; do not sed credentials into code.
    override = '\n# Xibo Pi deployment overrides\n' + ''.join(
        f'{key} = {value!r}\n' for key, value in values.items())
    write_private(config, example + override)
    print('MQTT monitor configured (credentials saved only on this Pi)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configure', action='store_true')
    parser.add_argument('--mqtt', action='store_true')
    args = parser.parse_args()
    home = Path.home()
    configure_player(home, args.configure)
    if args.mqtt:
        configure_monitor(home, getpass.getuser())
