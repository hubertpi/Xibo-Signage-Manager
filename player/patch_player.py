#!/usr/bin/env python3
"""Apply only the setup-page startup guard verified during the Pi deployment.

No iframe scaling patch is applied: the live layout worked without it.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess

MARKER = '/* xsm-playback-page-only */'
PWA_VERSION = '0.7.22'
STATUS_MARKER = '/* xsm-layout-start-report */'


def report_layout_start(text):
    if STATUS_MARKER in text:
        return text
    # Restrict the edit to the layoutStart event, after core records the active
    # ID and running state. The original PWA only reports at layoutEnd.
    event = re.search(r'this\.renderer\.on\([`\"]layoutStart[`\"],\(([\w$]+),[\w$]+\)=>\{', text)
    if not event:
        raise ValueError('Unexpected layoutStart handler; no player files changed')
    call = 'this.core.setCurrentLayout(' + event.group(1) + ')'
    index = text.find(call, event.end())
    if index < 0 or index - event.end() > 500:
        raise ValueError('Unexpected current-layout assignment; no player files changed')
    updated = '(' + call + ',' + STATUS_MARKER + 'this.core.notifyLayoutStatus(' + event.group(1) + '))'
    return text[:index] + updated + text[index + len(call):]


def guard_bundle(text):
    if MARKER in text or 'if(!document.getElementById(`player-container`))return;' in text:
        return text
    # v0.7.22 Vite bundle. Match the bootstrap, not every class constructor.
    pattern = r'(function [\w$]+\(\)\{)(let ([\w$]+)=new [\w$]+;\3\.init\(\)\.catch\()'
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError('Unexpected player bootstrap; no player files changed')
    match = matches[0]
    insert = match.end(1)
    return text[:insert] + MARKER + 'if(!document.getElementById("player-container"))return;' + text[insert:]


def patch(dist):
    manifest = dist.parent / 'package.json'
    version = json.loads(manifest.read_text())['version']
    # Other releases need validation before deploying them with this recipe.
    if version != PWA_VERSION:
        raise ValueError(f'Unvalidated bundled PWA version {version}; expected {PWA_VERSION}')
    candidates = list((dist / 'assets').glob('main-*.js'))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one main player bundle')
    path = candidates[0]
    current = path.read_text()
    updated = report_layout_start(guard_bundle(current))
    if updated != current:
        subprocess.run(['node', '--input-type=module', '--check'], input=updated,
                       text=True, capture_output=True, check=True)
        backup = path.with_name(path.name + '.before-xsm-setup-guard')
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(updated)
    # Remove the temporary HTTP-response diagnostic from the live session,
    # preserving any other HTML edits rather than restoring the whole file.
    index = dist / 'index.html'
    html = index.read_text()
    cleaned = re.sub(r'<script>\s*/\* xmds-response-diagnostic \*/.*?</script>',
                     '', html, flags=re.S)
    if cleaned != html:
        index.write_text(cleaned)
    print(f'PWA {version}: setup guard and layout-start reporting ready (no scaling changes)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=pathlib.Path, default=pathlib.Path(
        '/usr/libexec/xiboplayer-chromium/server/node_modules/@xiboplayer/pwa/dist'))
    args = parser.parse_args()
    patch(args.dist)
