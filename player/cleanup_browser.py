#!/usr/bin/env python3
"""Close only this user's Chromium processes using the dedicated Xibo profile.

Chromium can survive its launcher outside the service cgroup. Leaving it there
causes the next launcher to reuse that browser and immediately stop its server.
No profile files or Chromium singleton locks are removed.
"""
import os
from pathlib import Path
import select
import shlex
import signal
import time


def matches_process(proc, profile, uid):
    try:
        if proc.stat().st_uid != uid:
            return False
        executable = Path(os.readlink(proc / 'exe')).name.removesuffix(' (deleted)')
        if executable not in ('chromium', 'chromium-browser'):
            return False
        args = [arg for arg in (proc / 'cmdline').read_bytes().decode(
            errors='replace').split('\0') if arg]
        # Chromium can rewrite its process title so /proc exposes argv as one
        # space-separated string. Match that representation as well as normal
        # NUL-separated argv; never execute the parsed text.
        if len(args) == 1:
            args = shlex.split(args[0])
        values = []
        for index, arg in enumerate(args):
            if arg.startswith('--user-data-dir='):
                values.append(arg.split('=', 1)[1])
            elif arg == '--user-data-dir' and index + 1 < len(args):
                values.append(args[index + 1])
        # Chromium uses the last occurrence of a command-line switch.
        return bool(values) and os.path.abspath(values[-1]) == os.path.abspath(profile)
    except (OSError, ValueError):
        # Processes can disappear while /proc is being inspected.
        return False


def wait_for_exit(descriptors, timeout):
    pending = set(descriptors)
    poller = select.poll()
    for descriptor in pending:
        poller.register(descriptor, select.POLLIN)
    deadline = time.monotonic() + timeout
    while pending:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        for descriptor, _ in poller.poll(max(1, int(remaining * 1000))):
            pending.discard(descriptor)
            poller.unregister(descriptor)
    return pending


def send(descriptor, signum):
    try:
        signal.pidfd_send_signal(descriptor, signum)
    except ProcessLookupError:
        pass


def cleanup(profile, grace=5):
    descriptors = []
    try:
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit() or int(proc.name) == os.getpid():
                continue
            # Select first, then open a stable process reference and revalidate.
            # pidfds prevent accidentally signalling a reused PID.
            if not matches_process(proc, profile, os.getuid()):
                continue
            try:
                descriptor = os.pidfd_open(int(proc.name))
            except ProcessLookupError:
                continue
            if not matches_process(proc, profile, os.getuid()):
                os.close(descriptor)
                continue
            descriptors.append(descriptor)
        if not descriptors:
            return
        print(f'Closing {len(descriptors)} leftover Xibo Chromium process(es)', flush=True)
        for descriptor in descriptors:
            send(descriptor, signal.SIGTERM)
        remaining = wait_for_exit(descriptors, grace)
        for descriptor in remaining:
            send(descriptor, signal.SIGKILL)
        if remaining and wait_for_exit(remaining, 2):
            raise RuntimeError('Xibo Chromium did not exit; refusing a conflicting launch')
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


if __name__ == '__main__':
    cleanup(Path.home() / '.local/share/xiboplayer/chromium')
