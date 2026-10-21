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


def guard_bundle(text):
    if MARKER in text or 'if(!document.getElementById(`player-container`))return;' in text:
        return text
    # v0.7.15 Vite bundle. Match the bootstrap, not every class constructor.
    pattern = r'(function [\w$]+\(\)\{)(let ([\w$]+)=new [\w$]+;\3\.init\(\)\.catch\()'
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError('Unexpected v0.7.15 bootstrap; no player files changed')
    match = matches[0]
    insert = match.end(1)
    return text[:insert] + MARKER + 'if(!document.getElementById("player-container"))return;' + text[insert:]


def patch(dist):
    manifest = dist.parent / 'package.json'
    version = json.loads(manifest.read_text())['version']
    # Other releases need validation before deploying them with this recipe.
    if version != '0.7.15':
        raise ValueError(f'Unvalidated bundled PWA version {version}; expected 0.7.15')
    candidates = list((dist / 'assets').glob('main-*.js'))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one main player bundle')
    path = candidates[0]
    current = path.read_text()
    updated = guard_bundle(current)
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
    print(f'PWA {version}: playback-page guard ready (no scaling changes)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=pathlib.Path, default=pathlib.Path(
        '/usr/libexec/xiboplayer-chromium/server/node_modules/@xiboplayer/pwa/dist'))
    args = parser.parse_args()
    patch(args.dist)
