"""Small, read-only adapter around the MIT-licensed weread-omni CLI.

Authentication belongs to weread-omni; this module never handles or logs cookies.
"""

from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

from weread_pacing import PacingBlocked, WeReadPacer

CLI_VERSION = "0.1.2"
MIN_UNVERIFIED_BODY_CHARACTERS = 80
ACCOUNT_ID = re.compile(r"^MP_WXS_[0-9]+$")
INSTALL_PREFIX = Path.home() / ".local/share/wechat-download-skill/weread-omni"
INSTALL_SCRIPT = Path(__file__).with_name("install_weread_cli.sh")


class WeReadError(RuntimeError):
    """An authentication, transport, or upstream API failure."""

    def __init__(self, message, *, code=None, account_name=None, status=None,
                 review_id=None, article_title=None, published_at=None):
        super().__init__(message)
        self.code = code
        self.account_name = account_name
        self.status = status
        self.review_id = review_id
        self.article_title = article_title
        self.published_at = published_at


def executable_path():
    configured = os.environ.get("WEREAD_CLI")
    if configured:
        found = shutil.which(configured)
        if found:
            return found
        raise WeReadError("WEREAD_CLI does not point to an executable")
    installed = INSTALL_PREFIX / "node_modules/.bin/weread-omni"
    if installed.is_file():
        return str(installed)
    found = shutil.which("weread-omni")
    if found:
        return found
    raise WeReadError("WeRead CLI is missing; run: bash {}".format(INSTALL_SCRIPT))


def article_url(value):
    """Accept only public WeChat article URLs (not arbitrary fetch targets)."""
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != "mp.weixin.qq.com":
        return None
    try:
        if parsed.username or parsed.password or parsed.port:
            return None
    except ValueError:
        return None
    if parsed.path != "/s" and not parsed.path.startswith("/s/"):
        return None
    return value


def _find_article_url(obj, depth=0):
    if depth > 4 or not isinstance(obj, dict):
        return None
    for key in ("doc_url", "docUrl", "sourceUrl", "url"):
        found = article_url(obj.get(key))
        if found:
            return found
    for key in ("mpInfo", "review", "data", "article"):
        found = _find_article_url(obj.get(key), depth + 1)
        if found:
            return found
    return None


class WeReadClient:
    def __init__(self, executable=None, account=None, refresh=False, runner=None, pacer=None):
        self.executable = executable or executable_path()
        self.account = account or os.environ.get("WEREAD_ACCOUNT", "default")
        self.refresh = refresh
        self.runner = runner or subprocess.run
        # A supplied runner is a test seam; real CLI calls always share the on-disk gate.
        self.pacer = pacer if pacer is not None else (WeReadPacer() if runner is None else None)

    def command(self, *parts, refresh=None):
        base = [self.executable, "--account", self.account, "--json"]
        if self.refresh if refresh is None else refresh:
            base.append("--refresh")
        return base + [str(part) for part in parts]

    def call(self, *parts, timeout=90, refresh=None):
        guard = self.pacer.request() if self.pacer is not None and parts[0] not in ("doctor", "login") else nullcontext()
        try:
            with guard:
                return self._run(*parts, timeout=timeout, refresh=refresh)
        except PacingBlocked as exc:
            raise WeReadError(str(exc), code=exc.code) from exc

    def _run(self, *parts, timeout=90, refresh=None):
        try:
            completed = self.runner(self.command(*parts, refresh=refresh), capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise WeReadError("WeRead request timed out") from exc
        except OSError as exc:
            raise WeReadError("Cannot start WeRead CLI: {}".format(exc)) from exc
        if completed.returncode != 0:
            lines = completed.stderr.strip().splitlines()
            detail = lines[-1][:500] if lines else "unknown error"
            try:
                payload = json.loads(lines[-1]) if lines else {}
            except ValueError:
                payload = {}
            payload = payload if isinstance(payload, dict) else {}
            article = payload.get("article")
            article = article if isinstance(article, dict) else {}
            message = payload.get("error")
            message = message if isinstance(message, str) else detail
            code = payload.get("code")
            code = code if isinstance(code, str) else None
            # Do not log the full upstream article payload or any credentials.
            label = "{} [{}]".format(message, code) if code else message
            raise WeReadError("WeRead CLI failed (exit {}): {}".format(completed.returncode, label[:500]),
                              code=code, account_name=article.get("accountName"), status=payload.get("status"),
                              review_id=article.get("reviewId"), article_title=article.get("title"),
                              published_at=article.get("publishedAt"))
        try:
            return json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise WeReadError("WeRead CLI returned invalid JSON") from exc

    def search(self, query):
        return self.call("search", "books", query, "--scope", "2")

    def articles(self, account_id, count=20, offset=None):
        if not ACCOUNT_ID.fullmatch(account_id):
            raise WeReadError("Expected a WeRead account ID (MP_WXS_<digits>), not a legacy fakeid")
        if count < 1 or count > 50 or offset is not None and offset < 0:
            raise WeReadError("Invalid article page range")
        parts = ["public-accounts", "articles", account_id, "--count", count]
        if offset is not None:
            parts.extend(["--offset", offset])
        result = self.call(*parts)
        if not isinstance(result, dict) or not isinstance(result.get("articles"), list):
            raise WeReadError("WeRead article list has an unexpected response shape")
        return result

    def resolve_url(self, entry):
        url = _find_article_url(entry)
        if url:
            return url
        review_id = entry.get("reviewId") if isinstance(entry, dict) else None
        if isinstance(review_id, str) and review_id:
            return _find_article_url(self.call("review", "single", review_id))
        return None

    def read(self, url, refresh=None):
        if not article_url(url):
            raise WeReadError("Expected a public https://mp.weixin.qq.com/s article URL")
        result = self.call("public-accounts", "read-article", url, timeout=150, refresh=refresh)
        if not isinstance(result, dict):
            raise WeReadError("WeRead article response has an unexpected shape")
        if result.get("status") != "readable":
            raise WeReadError("WeRead did not return a readable full article",
                              code="SOURCE_CONTENT_UNAVAILABLE", account_name=result.get("accountName"))
        markdown = result.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            raise WeReadError("WeRead returned no readable article text")
        # A WeChat anti-scraping shell may contain only the author and controls while
        # weread-omni still marks it "readable" with completeness="unverified".
        # Fail closed instead of writing metadata and calling it a full article.
        substantive = markdown
        for label in ("阅读原文", "不喜欢", "原创", str(result.get("accountName") or "")):
            if label:
                substantive = substantive.replace(label, "")
        if (result.get("completeness") != "verified"
                and len(re.sub(r"\s+", "", substantive)) < MIN_UNVERIFIED_BODY_CHARACTERS):
            raise WeReadError("WeRead returned only a short, unverified article preview; full body unavailable",
                              code="SOURCE_CONTENT_INSUFFICIENT", account_name=result.get("accountName"))
        return result
