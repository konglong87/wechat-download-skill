"""Cross-process pacing and circuit breaking for the authenticated WeRead CLI.

Only timestamps and counters are persisted; authentication never passes through here.
The lock spans the CLI call so parallel scheduled jobs cannot generate a burst.
"""

from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import random
import tempfile
import time

STATE_PATH = Path.home() / ".local/state/wechat-download-skill/weread-pacing.json"
STATE_VERSION = 1
MIN_INTERVAL_SECONDS = 5
INTERVAL_JITTER_SECONDS = 5
THROTTLE_BASE_SECONDS = 60
THROTTLE_CAP_SECONDS = 30 * 60
THROTTLE_JITTER_FRACTION = 0.25
MAX_THROTTLE_LEVEL = 6
CHALLENGE_BASE_SECONDS = 30 * 60
CHALLENGE_CAP_SECONDS = 24 * 60 * 60
MAX_CHALLENGE_LEVEL = 8
MAX_INLINE_WAIT_SECONDS = 15
CHALLENGE_MARKERS = ("-2041", "human verification", "verification challenge", "captcha", "人机验证", "人工验证")
THROTTLE_MARKERS = ("freq control", "rate limit", "too many requests")


class PacingBlocked(RuntimeError):
    """The on-disk gate prevents another authenticated request."""

    def __init__(self, message, code="PACING_STATE_UNAVAILABLE"):
        super().__init__(message)
        self.code = code


def _default_state():
    return {"version": STATE_VERSION, "next_allowed_at": 0.0, "throttle_level": 0,
            "verification_required": False, "challenge_at": 0.0, "challenge_level": 0}


class WeReadPacer:
    def __init__(self, state_path=STATE_PATH, clock=time.time, sleep=time.sleep, jitter=random.uniform):
        self.path = Path(state_path)
        self.clock = clock
        self.sleep = sleep
        self.jitter = jitter

    @contextmanager
    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self):
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return _default_state()
        except (OSError, ValueError) as exc:
            raise PacingBlocked("WeRead pacing state cannot be read; refusing to send a request") from exc
        if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
            raise PacingBlocked("WeRead pacing state is invalid; refusing to send a request")
        defaults = _default_state()
        for key in ("next_allowed_at", "challenge_at"):
            value = state.get(key)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise PacingBlocked("WeRead pacing state is invalid; refusing to send a request")
        level = state.get("throttle_level")
        challenge_level = state.get("challenge_level")
        if (type(level) is not int or not 0 <= level <= MAX_THROTTLE_LEVEL
                or type(challenge_level) is not int or not 0 <= challenge_level <= MAX_CHALLENGE_LEVEL
                or type(state.get("verification_required")) is not bool):
            raise PacingBlocked("WeRead pacing state is invalid; refusing to send a request")
        return {key: state[key] for key in defaults}

    def _write(self, state):
        fd, temporary = tempfile.mkstemp(prefix=".weread-pacing-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(state, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def status(self):
        with self._lock():
            return self._read()

    def _challenge(self, state):
        state["verification_required"] = True
        state["challenge_at"] = self.clock()
        state["challenge_level"] = min(MAX_CHALLENGE_LEVEL, state["challenge_level"] + 1)
        backoff = min(CHALLENGE_CAP_SECONDS, CHALLENGE_BASE_SECONDS * 2 ** (state["challenge_level"] - 1))
        state["next_allowed_at"] = max(state["next_allowed_at"], self.clock() +
                                         min(CHALLENGE_CAP_SECONDS, backoff *
                                             (1 + self.jitter(0, THROTTLE_JITTER_FRACTION))))

    def mark_challenge(self):
        """Import an observed -2041 without issuing another request."""
        with self._lock():
            state = self._read()
            self._challenge(state)
            self._write(state)

    def clear_verified_challenge(self):
        """Explicitly resume early only after official-client verification."""
        with self._lock():
            state = self._read()
            state["verification_required"] = False
            state["challenge_at"] = 0.0
            state["challenge_level"] = 0
            state["next_allowed_at"] = self.clock() + MIN_INTERVAL_SECONDS
            self._write(state)

    @contextmanager
    def request(self):
        with self._lock():
            state = self._read()
            remaining = max(0.0, state["next_allowed_at"] - self.clock())
            if state["verification_required"] and remaining:
                raise PacingBlocked("WeRead -2041 verification challenge: next single probe in {:.0f}s; no request sent. If verified in the official client, run 'python3 scripts/download_weread.py pace-reset --verified'".format(remaining), code="HUMAN_VERIFICATION_REQUIRED")
            if remaining > MAX_INLINE_WAIT_SECONDS:
                raise PacingBlocked("WeRead rate limit cooldown active for another {:.0f}s; no request sent".format(remaining), code="PACING_COOLDOWN")
            if remaining:
                self.sleep(remaining)
            state["next_allowed_at"] = self.clock() + MIN_INTERVAL_SECONDS + self.jitter(0, INTERVAL_JITTER_SECONDS)
            self._write(state)  # Commit a reservation before touching the remote CLI.
            try:
                yield
            except Exception as exc:
                message = str(exc).lower()
                if any(marker in message for marker in CHALLENGE_MARKERS):
                    self._challenge(state)
                elif getattr(exc, "status", None) == 429 or any(marker in message for marker in THROTTLE_MARKERS):
                    state["throttle_level"] = min(MAX_THROTTLE_LEVEL, state["throttle_level"] + 1)
                    backoff = min(THROTTLE_CAP_SECONDS, THROTTLE_BASE_SECONDS * 2 ** (state["throttle_level"] - 1))
                    state["next_allowed_at"] = max(state["next_allowed_at"], self.clock() +
                                                     min(THROTTLE_CAP_SECONDS, backoff *
                                                         (1 + self.jitter(0, THROTTLE_JITTER_FRACTION))))
                if state["verification_required"] and not any(marker in message for marker in CHALLENGE_MARKERS):
                    # An inconclusive probe does not prove the verification has cleared.
                    state["next_allowed_at"] = max(state["next_allowed_at"],
                                                     self.clock() + CHALLENGE_BASE_SECONDS)
                self._write(state)
                raise
            else:
                state["throttle_level"] = max(0, state["throttle_level"] - 1)
                state["verification_required"] = False
                state["challenge_level"] = 0
                state["challenge_at"] = 0.0
                self._write(state)
