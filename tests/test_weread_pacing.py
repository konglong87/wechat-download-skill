import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from weread_client import WeReadClient, WeReadError
from weread_pacing import PacingBlocked, WeReadPacer


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.delays = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.delays.append(seconds)
        self.now += seconds


class WeReadPacingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.clock = FakeClock()
        self.path = Path(self.directory.name) / "pacing.json"
        self.pacer = WeReadPacer(self.path, clock=self.clock.clock, sleep=self.clock.sleep,
                                jitter=lambda low, high: 0)

    def test_successive_requests_are_spaced_across_instances(self):
        with self.pacer.request():
            pass
        with WeReadPacer(self.path, clock=self.clock.clock, sleep=self.clock.sleep,
                         jitter=lambda low, high: 0).request():
            pass
        self.assertEqual(self.clock.delays, [5])
        self.assertEqual(self.pacer.status()["next_allowed_at"], 1010)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_throttling_exponential_backoff_and_success_recovery(self):
        with self.assertRaisesRegex(WeReadError, "freq control"):
            with self.pacer.request():
                raise WeReadError("freq control")
        self.assertEqual(self.pacer.status()["throttle_level"], 1)
        self.assertEqual(self.pacer.status()["next_allowed_at"], 1060)
        with self.assertRaises(PacingBlocked) as blocked:
            with self.pacer.request():
                self.fail("cooldown did not stop the request")
        self.assertEqual(blocked.exception.code, "PACING_COOLDOWN")
        self.assertEqual(self.clock.delays, [])
        self.clock.now = 1060
        with self.assertRaises(WeReadError):
            with self.pacer.request():
                raise WeReadError("HTTP 429", status=429)
        self.assertEqual(self.pacer.status()["throttle_level"], 2)
        self.assertEqual(self.pacer.status()["next_allowed_at"], 1180)
        self.clock.now = 1180
        with self.pacer.request():
            pass
        self.assertEqual(self.pacer.status()["throttle_level"], 1)

    def test_challenge_persists_and_requires_explicit_reset(self):
        runner = Mock(return_value=Mock(returncode=1, stdout="", stderr="mobile /store/search: human verification challenge (-2041)"))
        client = WeReadClient(executable="/stub", runner=runner, pacer=self.pacer)
        with self.assertRaisesRegex(WeReadError, "-2041"):
            client.search("孔小黑进城")
        self.assertTrue(self.pacer.status()["verification_required"])
        self.assertEqual(runner.call_count, 1)
        with self.assertRaises(WeReadError) as blocked:
            WeReadClient(executable="/stub", runner=runner, pacer=self.pacer).search("孔小黑进城")
        self.assertEqual(blocked.exception.code, "HUMAN_VERIFICATION_REQUIRED")
        self.assertEqual(runner.call_count, 1)
        # Doctor is local authentication inspection; it is always allowed.
        runner.return_value = Mock(returncode=0, stdout=json.dumps({"auth": "authenticated"}), stderr="")
        self.assertEqual(client.call("doctor"), {"auth": "authenticated"})
        self.assertEqual(self.pacer.status()["next_allowed_at"], 2800)
        self.clock.now = 2800
        runner.return_value = Mock(returncode=0, stdout=json.dumps({"ok": True}), stderr="")
        self.assertEqual(client.search("孔小黑进城"), {"ok": True})  # Only one probe after cooling.
        self.assertFalse(self.pacer.status()["verification_required"])
        self.assertEqual(self.pacer.status()["challenge_level"], 0)
        self.assertEqual(runner.call_count, 3)  # First challenge, doctor, one probe.

    def test_corrupt_state_fails_closed_without_cli_call(self):
        self.path.write_text('{"version": 1, "next_allowed_at": "never"}', encoding="utf-8")
        runner = Mock()
        client = WeReadClient(executable="/stub", runner=runner, pacer=self.pacer)
        with self.assertRaises(WeReadError) as blocked:
            client.search("孔小黑进城")
        self.assertEqual(blocked.exception.code, "PACING_STATE_UNAVAILABLE")
        runner.assert_not_called()

    def test_known_challenge_can_be_imported_without_another_request(self):
        self.pacer.mark_challenge()
        self.assertTrue(self.pacer.status()["verification_required"])
        self.assertEqual(self.pacer.status()["challenge_at"], 1000)
        with self.assertRaises(PacingBlocked):
            with self.pacer.request():
                self.fail("should not execute")
        self.clock.now = 2800
        with self.assertRaises(WeReadError):
            with self.pacer.request():
                raise WeReadError("human verification challenge (-2041)")
        self.assertEqual(self.pacer.status()["challenge_level"], 2)
        self.assertEqual(self.pacer.status()["next_allowed_at"], 6400)  # Double the cooldown.
        self.pacer.clear_verified_challenge()
        self.assertFalse(self.pacer.status()["verification_required"])
        self.assertEqual(self.pacer.status()["next_allowed_at"], 2805)


if __name__ == "__main__":
    unittest.main()
