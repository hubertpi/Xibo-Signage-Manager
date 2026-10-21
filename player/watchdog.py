#!/usr/bin/env python3
"""Local-only health watchdog. Never reboots the Pi or checks CMS availability."""
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler

UNIT = 'xiboplayer-chromium.service'


def decide(active, healthy, failures, last_restart, now, paused=False, age=999):
    if paused or active in ('inactive', 'deactivating', 'activating') or age < 60:
        return 'skip', 0
    if healthy:
        return 'healthy', 0
    failures += 1
    if failures >= 3 and now - last_restart >= 120:
        return 'restart', 0
    return 'wait', failures


def get_json(url):
    # Do not route localhost health requests through corporate proxy settings.
    opener = build_opener(ProxyHandler({}))
    with opener.open(url, timeout=5) as response:
        return json.load(response)


def healthy_renderer():
    import websocket
    opener = build_opener(ProxyHandler({}))
    with opener.open('http://127.0.0.1:8766/player/index.html', timeout=5) as response:
        if response.status != 200:
            return False
    targets = get_json('http://127.0.0.1:9222/json/list')
    for target in targets:
        parsed = urlsplit(target.get('url', ''))
        if target.get('type') != 'page' or parsed.hostname not in ('localhost', '127.0.0.1'):
            continue
        if parsed.port != 8766 or not parsed.path.startswith('/player/'):
            continue
        debugger = target.get('webSocketDebuggerUrl', '')
        if urlsplit(debugger).hostname not in ('localhost', '127.0.0.1'):
            continue
        connection = websocket.create_connection(debugger, timeout=5,
                                                  suppress_origin=True,
                                                  http_no_proxy=['localhost', '127.0.0.1'])
        try:
            connection.send(json.dumps({'id': 7, 'method': 'Runtime.evaluate',
                                        'params': {'expression': 'document.readyState',
                                                   'returnByValue': True}}))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                connection.settimeout(max(0.1, deadline - time.monotonic()))
                result = json.loads(connection.recv())
                if result.get('id') == 7:
                    return result.get('result', {}).get('result', {}).get('value') in ('interactive', 'complete')
        finally:
            connection.close()
    return False


def main():
    state_dir = Path.home() / '.local/state/xsm-player'
    state_dir.mkdir(parents=True, exist_ok=True)
    if (state_dir / 'paused').exists():
        return
    result = subprocess.run(['systemctl', '--user', 'show', UNIT,
                             '-p', 'ActiveState', '-p', 'ActiveEnterTimestampMonotonic'],
                            capture_output=True, text=True, check=True)
    properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    active = properties.get('ActiveState', 'inactive')
    if active in ('inactive', 'deactivating', 'activating'):
        # systemctl stop is intentional too. systemd handles unexpected exits.
        return
    started = int(properties.get('ActiveEnterTimestampMonotonic') or 0) / 1_000_000
    age = time.monotonic() - started if started else 999
    if age < 60:
        return
    state_path = state_dir / 'watchdog.json'
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    healthy = False
    try:
        healthy = active == 'active' and healthy_renderer()
    except Exception as error:
        print(f'Xibo health probe failed: {type(error).__name__}', flush=True)
    now = time.time()
    action, failures = decide(active, healthy, state.get('failures', 0),
                              state.get('last_restart', 0), now, age=age)
    if action == 'restart':
        # Recheck the intentional-stop flag immediately before recovery.
        if (state_dir / 'paused').exists():
            return
        latest = subprocess.check_output(
            ['systemctl', '--user', 'show', UNIT, '-p', 'ActiveState', '--value'],
            text=True).strip()
        if latest in ('inactive', 'deactivating'):
            return
        print('Xibo failed three health checks; restarting the player', flush=True)
        subprocess.run(['systemctl', '--user', 'reset-failed', UNIT], check=True)
        subprocess.run(['systemctl', '--user', 'restart', UNIT], check=True)
        state['last_restart'] = now
    state['failures'] = failures
    state_path.write_text(json.dumps(state))


if __name__ == '__main__':
    main()
