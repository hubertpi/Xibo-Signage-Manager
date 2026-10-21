import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cleanup_browser', ROOT / 'cleanup_browser.py')
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


class SelectionTests(unittest.TestCase):
    def test_only_exact_profile_executable_and_user_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root / 'chromium'
            binary.touch()
            proc = root / 'process'
            proc.mkdir()
            (proc / 'exe').symlink_to(binary)
            profile = root / 'xibo'
            def command(*args):
                (proc / 'cmdline').write_bytes(('chromium\0' + '\0'.join(args) + '\0').encode())
            command('--user-data-dir=' + str(profile))
            self.assertTrue(browser.matches_process(proc, profile, os.getuid()))
            self.assertFalse(browser.matches_process(proc, profile, os.getuid() + 1))
            command('--user-data-dir', str(profile))
            self.assertTrue(browser.matches_process(proc, profile, os.getuid()))
            command('--user-data-dir=' + str(profile) + '-other')
            self.assertFalse(browser.matches_process(proc, profile, os.getuid()))
            command('--title=--user-data-dir=' + str(profile))
            self.assertFalse(browser.matches_process(proc, profile, os.getuid()))
            command('--user-data-dir=' + str(profile), '--user-data-dir=/other')
            self.assertFalse(browser.matches_process(proc, profile, os.getuid()))
            command('--user-data-dir=' + str(profile))
            (proc / 'exe').unlink()
            (proc / 'exe').symlink_to(root / 'other-app')
            self.assertFalse(browser.matches_process(proc, profile, os.getuid()))
            (proc / 'exe').unlink()
            (proc / 'exe').symlink_to(root / 'chromium (deleted)')
            self.assertTrue(browser.matches_process(proc, profile, os.getuid()))

    def test_disappeared_process_is_ignored(self):
        self.assertFalse(browser.matches_process(Path('/proc/no-such-process'), '/profile', os.getuid()))


@unittest.skipUnless(shutil.which('cc') and hasattr(os, 'pidfd_open'), 'requires Linux pidfds and a C compiler')
class ProcessCleanupTests(unittest.TestCase):
    def test_real_process_cleanup_preserves_other_profiles_and_apps(self):
        if not (Path('/proc') / str(os.getpid())).exists():
            self.skipTest('executor hides process namespace; exercised on Linux CI')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root / 'chromium'
            source = ('#include <signal.h>\n#include <unistd.h>\n'
                      'int main(int argc,char **argv){'
                      'if(argc>2)signal(SIGTERM,SIG_IGN);'
                      'write(1,"ready\\n",6);for(;;)pause();}')
            subprocess.run(['cc', '-x', 'c', '-', '-o', str(binary)], input=source,
                           text=True, check=True)
            other = root / 'other-app'
            shutil.copy2(binary, other)
            profile = root / 'xibo-profile'
            processes = []
            def launch(exe, selected_profile, stubborn=False):
                args = [str(exe), '--user-data-dir=' + str(selected_profile)]
                if stubborn:
                    args.append('ignore-term')
                process = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)
                processes.append(process)
                self.assertEqual(process.stdout.readline(), 'ready\n')
                return process
            try:
                normal = launch(binary, profile)
                stubborn = launch(binary, profile, True)
                unrelated = launch(binary, root / 'another-profile')
                other_app = launch(other, profile)
                browser.cleanup(profile, grace=0.1)
                self.assertEqual(normal.wait(timeout=2), -15)
                self.assertEqual(stubborn.wait(timeout=2), -9)
                self.assertIsNone(unrelated.poll())
                self.assertIsNone(other_app.poll())
                browser.cleanup(profile, grace=0.1)  # repeat is harmless
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=2)
                    process.stdout.close()


if __name__ == '__main__':
    unittest.main()
