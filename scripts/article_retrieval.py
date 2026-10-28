"""Bounded WeRead retries followed by an exact-item public RSS fallback."""

import sys
import time

from download_rss import RSSError
from rss_fallback import RSSFallback
from weread_client import WeReadError

MAX_READ_RETRIES = 3  # Three retries after the initial request.
RETRY_BACKOFF_SECONDS = (2, 4, 8)
TRANSIENT_SOURCE_CODES = frozenset(("SOURCE_CONTENT_INSUFFICIENT",))
TRANSIENT_HTTP_STATUS = frozenset((500, 502, 503, 504))
STOP_WORDS = ("freq control", "rate limit", "-2041", "验证", "captcha", "challenge",
              "verification", "access denied", "forbidden", "blocked", "登录")
TRANSIENT_WORDS = ("timed out", "timeout", "connection reset", "temporarily unavailable")


def retryable(error):
    message = str(error).lower()
    if any(word in message for word in STOP_WORDS):
        return False
    if isinstance(error.status, int) and error.status in TRANSIENT_HTTP_STATUS:
        return True
    return error.code in TRANSIENT_SOURCE_CODES or any(word in message for word in TRANSIENT_WORDS)


def read_article(client, url, account_name=None, fallback=None, sleep=time.sleep):
    """Try WeRead once plus three bounded retries; never retry a challenge."""
    fallback = fallback if fallback is not None else RSSFallback()
    last_error = None
    attempts = 0
    for retry in range(MAX_READ_RETRIES + 1):
        attempts += 1
        try:
            return client.read(url) if retry == 0 else client.read(url, refresh=True)
        except WeReadError as exc:
            last_error = exc
            account_name = exc.account_name or account_name
            if retry >= MAX_READ_RETRIES or not retryable(exc):
                break
            delay = RETRY_BACKOFF_SECONDS[retry]
            print("WeRead body unavailable; retry {}/{} in {}s".format(retry + 1, MAX_READ_RETRIES, delay), file=sys.stderr)
            sleep(delay)
    try:
        result = fallback.fetch(url, account_name)
    except RSSError as exc:
        raise WeReadError("WeRead failed after {} attempt(s): {}; RSS fallback unavailable: {}".format(
            attempts, last_error, exc), code=last_error.code) from exc
    print("Article matched and recovered from public RSS after {} WeRead attempt(s)".format(attempts), file=sys.stderr)
    return result
