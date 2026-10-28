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


def read_article(client, url, account_name=None, fallback=None, sleep=time.sleep,
                 web_client=None, review_id=None, title=None, published_at=None):
    """Try eInk, optional authenticated Web, then exact public RSS."""
    fallback = fallback if fallback is not None else RSSFallback()
    last_error = None
    attempts = 0
    web_error = None
    challenge_probed = False
    for retry in range(MAX_READ_RETRIES + 1):
        attempts += 1
        try:
            return client.read(url) if retry == 0 else client.read(url, refresh=True)
        except WeReadError as exc:
            last_error = exc
            account_name = exc.account_name or account_name
            review_id = exc.review_id or review_id
            title = exc.article_title or title
            published_at = exc.published_at or published_at
            if retry >= MAX_READ_RETRIES or not retryable(exc):
                break
            if exc.code == "SOURCE_CONTENT_INSUFFICIENT" and not challenge_probed:
                challenge_probed = True
                if getattr(client, "is_source_challenge", lambda _: False)(url):
                    print("WeChat source redirects to verification; skip futile body retries", file=sys.stderr)
                    break
            delay = RETRY_BACKOFF_SECONDS[retry]
            print("WeRead body unavailable; retry {}/{} in {}s".format(retry + 1, MAX_READ_RETRIES, delay), file=sys.stderr)
            sleep(delay)
    if web_client is not None and review_id and not any(
            word in str(last_error).lower() for word in ("freq control", "rate limit", "-2041")):
        try:
            return web_client.read(review_id, title=title, account_name=account_name, published_at=published_at)
        except WeReadError as exc:
            web_error = exc
            print("Authenticated WeRead Web body unavailable: {}".format(exc), file=sys.stderr)
    try:
        result = fallback.fetch(url, account_name)
    except RSSError as exc:
        web_detail = "; WeRead Web: {}".format(web_error) if web_error is not None else ""
        raise WeReadError("WeRead failed after {} attempt(s): {}{}; RSS fallback unavailable: {}".format(
            attempts, last_error, web_detail, exc), code=last_error.code) from exc
    print("Article matched and recovered from public RSS after {} WeRead attempt(s)".format(attempts), file=sys.stderr)
    return result
