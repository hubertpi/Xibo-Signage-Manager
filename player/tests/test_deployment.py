import importlib.util
import json
import os
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


config = module('configure')
guard = module('patch_player')
watchdog = module('watchdog')


class SetupGuardTests(unittest.TestCase):
    bundle = 'function boot(){let e=new Player;e.init().catch(()=>{});}boot();'

    def test_setup_page_does_not_construct_player_but_playback_does(self):
        fixed = guard.guard_bundle(self.bundle)
        for present, expected in ((False, 0), (True, 1)):
            prefix = ('let calls=0;class Player{constructor(){calls++;}'
                      'init(){return Promise.resolve();}}'
                      f'const document={{getElementById:()=>{str(present).lower()}}};')
            result = subprocess.check_output(
                ['node', '-e', prefix + fixed + 'console.log(calls);'], text=True)
            self.assertEqual(int(result), expected)

    def test_idempotent_and_existing_live_fix_preserved(self):
        fixed = guard.guard_bundle(self.bundle)
        self.assertEqual(guard.guard_bundle(fixed), fixed)
        manual = self.bundle.replace('{let e=', '{if(!document.getElementById(`player-container`))return;let e=')
        self.assertEqual(guard.guard_bundle(manual), manual)

    def test_ambiguous_bootstrap_fails(self):
        with self.assertRaises(ValueError):
            guard.guard_bundle(self.bundle + self.bundle)

    def test_unvalidated_release_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dist = root / 'dist'
            dist.mkdir()
            (root / 'package.json').write_text('{"version":"9.0.0"}')
            with self.assertRaises(ValueError):
                guard.patch(dist)
            self.assertEqual(list(dist.iterdir()), [])

    def test_installed_0722_manifest_is_accepted_and_patch_is_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dist = root / 'dist'
            assets = dist / 'assets'
            assets.mkdir(parents=True)
            (root / 'package.json').write_text('{"version":"0.7.22"}')
            bundle = assets / 'main-DZuP3atR.js'
            original = self.bundle + 'function bind(){this.renderer.on(`layoutStart`,(id,layout)=>{this.core.setCurrentLayout(id);});}'
            bundle.write_text(original)
            index = dist / 'index.html'
            index.write_text('<head><script>/* xmds-response-diagnostic */test()</script><title>Keep</title></head>')
            guard.patch(dist)
            fixed = bundle.read_text()
            self.assertIn(guard.MARKER, fixed)
            backup = assets / 'main-DZuP3atR.js.before-xsm-setup-guard'
            self.assertEqual(backup.read_text(), original)
            guard.patch(dist)
            self.assertEqual(bundle.read_text(), fixed)
            self.assertEqual(backup.read_text(), original)
            self.assertEqual(index.read_text(), '<head><title>Keep</title></head>')

    def test_layout_report_occurs_on_start_after_core_state_is_set(self):
        source = 'function bind(){this.renderer.on(`layoutStart`,(id,layout)=>{this.core.setCurrentLayout(id);});}'
        fixed = guard.report_layout_start(source)
        self.assertEqual(guard.report_layout_start(fixed), fixed)
        harness = fixed + '''
const calls=[];let handler;
const player={renderer:{on(name,fn){handler=fn;}},core:{
setCurrentLayout(id){calls.push(['set',id]);},
notifyLayoutStatus(id){calls.push(['notify',id]);}}};
bind.call(player);handler(24,{});
console.log(JSON.stringify(calls));'''
        result = subprocess.check_output(['node', '-e', harness], text=True)
        self.assertEqual(json.loads(result), [['set',24],['notify',24]])
        with self.assertRaises(ValueError):
            guard.report_layout_start('unrecognised bundle')


class ConfigurationTests(unittest.TestCase):
    def test_repair_preserves_credentials_identity_and_custom_settings(self):
        previous = dict(cmsKey='secret', hardwareKey='identity', cmsUrl='http://cms',
                        custom='keep', extraBrowserFlags='--foo --v=1')
        result = config.player_config(previous)
        for key in ('cmsKey', 'hardwareKey', 'cmsUrl', 'custom'):
            self.assertEqual(result[key], previous[key])
        self.assertEqual(result['extraBrowserFlags'], '--foo --v=0')
        self.assertEqual(config.player_config(result), result)
        self.assertTrue(result['hideMouseCursor'])

    def test_secret_permissions_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config'
            path.touch(mode=0o644)
            secret = 'quote\' backslash\\ newline\n$(echo no)'
            config.write_private(path, json.dumps({'key': secret}))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())['key'], secret)

    def test_monitor_credentials_can_be_serialized_as_python_literals(self):
        values = config.monitor_overrides({'mqtt_password': '\'\\\n'}, 'admin')
        source = ''.join(f'{key}={value!r}\n' for key, value in values.items())
        restored = {}
        exec(compile(source, '<config>', 'exec'), {}, restored)
        self.assertEqual(restored['mqtt_password'], '\'\\\n')
        self.assertTrue(restored['apt_updates'])
        self.assertFalse(restored['update'])
        self.assertEqual(len(restored['custom_scripts']), 4)


class WatchdogTests(unittest.TestCase):
    def renderer_probe(self, target, ready='complete'):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        opener = MagicMock()
        opener.open.return_value = response
        connection = MagicMock()
        connection.recv.return_value = json.dumps({'id': 7, 'result': {'result': {'value': ready}}})
        websocket = SimpleNamespace(create_connection=MagicMock(return_value=connection))
        with patch.dict('sys.modules', websocket=websocket), \
                patch.object(watchdog, 'build_opener', return_value=opener), \
                patch.object(watchdog, 'get_json', return_value=[target]):
            result = watchdog.healthy_renderer()
        self.assertEqual(opener.open.call_args.args[0], 'http://localhost:8766/player/index.html')
        return result, websocket, connection

    def test_localhost_can_reach_an_ipv6_only_server(self):
        class Server(HTTPServer):
            address_family = socket.AF_INET6
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"healthy":true}')
            def log_message(self, *args):
                pass
        try:
            server = Server(('::1',0), Handler)
        except OSError:
            self.skipTest('IPv6 loopback unavailable')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            self.assertEqual(watchdog.get_json(f'http://localhost:{port}/'), {'healthy':True})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_probe_requires_javascript_response_and_closes_socket(self):
        target = dict(type='page', url='http://localhost:8766/player/index.html',
                      webSocketDebuggerUrl='ws://127.0.0.1:9222/devtools/page/test')
        result, websocket, connection = self.renderer_probe(target)
        self.assertTrue(result)
        self.assertTrue(websocket.create_connection.call_args.kwargs['suppress_origin'])
        connection.close.assert_called_once()
        result, _, _ = self.renderer_probe(target, ready='loading')
        self.assertFalse(result)

    def test_probe_rejects_external_browser_and_debugger_urls(self):
        for page, debugger in (
                ('http://example.com:8766/player/', 'ws://127.0.0.1:9222/test'),
                ('http://localhost:8766/player/', 'ws://example.com:9222/test')):
            result, websocket, _ = self.renderer_probe(
                dict(type='page', url=page, webSocketDebuggerUrl=debugger))
            self.assertFalse(result)
            websocket.create_connection.assert_not_called()

    def test_three_failures_required(self):
        failures = 0
        for expected in ('wait', 'wait', 'restart'):
            action, failures = watchdog.decide('active', False, failures, 0, 1000)
            self.assertEqual(action, expected)

    def test_success_resets_failure_count(self):
        self.assertEqual(watchdog.decide('active', True, 2, 0, 1000), ('healthy', 0))

    def test_cooldown_and_startup_grace(self):
        self.assertEqual(watchdog.decide('active', False, 2, 950, 1000)[0], 'wait')
        self.assertEqual(watchdog.decide('active', False, 2, 0, 1000, age=20)[0], 'skip')

    def test_intentional_stop_and_persistent_pause(self):
        for active in ('inactive', 'deactivating', 'activating'):
            self.assertEqual(watchdog.decide(active, False, 10, 0, 1000)[0], 'skip')
        self.assertEqual(watchdog.decide('active', False, 10, 0, 1000, paused=True)[0], 'skip')
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            state = home / '.local/state/xsm-player'
            state.mkdir(parents=True)
            (state / 'paused').touch()
            with patch.object(watchdog.Path, 'home', return_value=home), patch.object(watchdog.subprocess, 'run') as run:
                watchdog.main()
                run.assert_not_called()

    def test_stop_during_probe_is_not_reversed(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            state = home / '.local/state/xsm-player'
            state.mkdir(parents=True)
            (state / 'watchdog.json').write_text('{"failures":2}')
            response = subprocess.CompletedProcess([], 0, 'ActiveState=active\nActiveEnterTimestampMonotonic=1\n')
            with patch.object(watchdog.Path, 'home', return_value=home), \
                    patch.object(watchdog, 'healthy_renderer', return_value=False), \
                    patch.object(watchdog.subprocess, 'run', return_value=response) as run, \
                    patch.object(watchdog.subprocess, 'check_output', return_value='inactive\n'):
                watchdog.main()
                self.assertEqual(run.call_count, 1)


class ControlTests(unittest.TestCase):
    def test_stop_survives_login_then_start_clears_pause(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            binary = home / 'systemctl'
            log = home / 'commands'
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$COMMAND_LOG"\n')
            binary.chmod(0o755)
            env = dict(os.environ, HOME=folder, PATH=folder + ':' + os.environ['PATH'],
                       COMMAND_LOG=str(log), DISPLAY=':0', XAUTHORITY='/tmp/test-authority')
            def run(name, *args):
                subprocess.run(['sh', str(ROOT / name), *args], env=env, check=True)
            run('control.sh', 'stop')
            paused = home / '.local/state/xsm-player/paused'
            self.assertTrue(paused.exists())
            log.write_text('')
            run('session-start.sh')
            self.assertNotIn('--user start xiboplayer-chromium.service', log.read_text())
            self.assertIn('import-environment XAUTHORITY', log.read_text())
            run('control.sh', 'start')
            self.assertFalse(paused.exists())
            self.assertIn('--user start xiboplayer-chromium.service', log.read_text())


if __name__ == '__main__':
    unittest.main()
