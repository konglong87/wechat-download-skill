"""CLI-level smoke test: a -2041 stops the next process before a network call."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/download_weread.py"


class PacingCLITests(unittest.TestCase):
    def test_challenge_survives_process_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            stub = home / "stub-cli"
            log = home / "calls.log"
            stub.write_text('''#!/usr/bin/env python3
import os
from pathlib import Path
import sys
Path(os.environ["CALL_LOG"]).open("a", encoding="utf-8").write("called\\n")
sys.stderr.write("mobile /store/search: human verification challenge (-2041)\\n")
sys.exit(1)
''', encoding="utf-8")
            stub.chmod(0o700)
            env = dict(os.environ, HOME=str(home), WEREAD_CLI=str(stub), CALL_LOG=str(log))

            def invoke(*args):
                return subprocess.run([sys.executable, str(CLI), *args], cwd=ROOT,
                                      env=env, capture_output=True, text=True, timeout=10)

            first = invoke("search", "孔小黑进城")
            self.assertEqual(first.returncode, 1)
            self.assertIn("-2041", first.stderr)
            second = invoke("search", "孔小黑进城")
            self.assertEqual(second.returncode, 1)
            self.assertIn("no request sent", second.stderr)
            self.assertEqual(log.read_text(encoding="utf-8"), "called\n")
            status = invoke("pace-status")
            self.assertEqual(status.returncode, 0)
            self.assertTrue(json.loads(status.stdout)["verification_required"])
            self.assertEqual(log.read_text(encoding="utf-8"), "called\n")
            self.assertEqual(invoke("pace-reset").returncode, 1)
            self.assertEqual(invoke("pace-reset", "--verified").returncode, 0)
            self.assertFalse(json.loads(invoke("pace-status").stdout)["verification_required"])


    def test_parallel_jobs_do_not_issue_simultaneous_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            stub = home / "stub-cli"
            log = home / "calls.log"
            stub.write_text('''#!/usr/bin/env python3
import os
from pathlib import Path
import time
Path(os.environ["CALL_LOG"]).open("a", encoding="utf-8").write(str(time.time()) + "\\n")
print('{"books": []}')
''', encoding="utf-8")
            stub.chmod(0o700)
            env = dict(os.environ, HOME=str(home), WEREAD_CLI=str(stub), CALL_LOG=str(log))
            command = [sys.executable, str(CLI), "search", "测试"]
            first = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
            second = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            try:
                outputs = [first.communicate(timeout=20), second.communicate(timeout=20)]
            finally:
                for process in (first, second):
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
            self.assertEqual([first.returncode, second.returncode], [0, 0], outputs)
            stamps = sorted(float(line) for line in log.read_text(encoding="utf-8").splitlines())
            self.assertEqual(len(stamps), 2)
            self.assertGreaterEqual(stamps[1] - stamps[0], 4.5)


if __name__ == "__main__":
    unittest.main()
