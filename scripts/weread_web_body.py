"""Optional, read-only WeRead Web article body adapter.

A user's *web* session is separate from weread-omni's eInk session. Credentials
are read only from an explicitly configured, private local file and are never
included in errors, output, or a project-managed directory.
"""

from getpass import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from download_rss import article_text
from weread_client import WeReadError

WEB_CONTENT_URL = "https://weread.qq.com/web/mp/content"
DEFAULT_COOKIE_FILE = Path.home() / ".local/share/wechat-download-skill/weread-web.cookie"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REVIEW_ID = re.compile(r"^MP_WXS_[0-9]+_[-A-Za-z0-9_~]+$")
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_COOKIE_BYTES = 8192
MIN_BODY_CHARACTERS = 80
WEB_TIMEOUT_SECONDS = 20
USER_AGENT = "Mozilla/5.0 (compatible; wechat-download-skill/1.4)"
CHALLENGE_MARKERS = ("wappoc_appmsgcaptcha", "环境异常", "完成验证", "请输入验证码")
VOID_TAGS = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                       "meta", "param", "source", "track", "wbr"))
CONTENT_NOENCODE = re.compile(r'\bcontent_noencode\s*=\s*("(?:\\.|[^"\\])*")', re.S)
LOGIN_MARKERS = ("扫码登录", "登录微信读书")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise WeReadError("WeRead Web redirected; web login or verification is required", code="WEB_LOGIN_REQUIRED")


class ContentFragment(HTMLParser):
    """Select only the actual #js_content, not a full page's navigation shell."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.found = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            if tag not in VOID_TAGS:
                self.depth += 1
            self.parts.append(self.get_starttag_text())
        elif dict(attrs).get("id") == "js_content":
            self.depth = 1
            self.found = True
            self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if self.depth:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.depth:
            self.parts.append("</{}>".format(tag))
            if tag not in VOID_TAGS:
                self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.depth:
            self.parts.append("&{};".format(name))

    def handle_charref(self, name):
        if self.depth:
            self.parts.append("&#{};".format(name))


def extract_body(html):
    """Fail closed on login/challenge shells or a page without identifiable body."""
    if any(marker in html for marker in CHALLENGE_MARKERS):
        raise WeReadError("WeRead Web encountered a verification page; complete it manually", code="WEB_CHALLENGE")
    if any(marker in html for marker in LOGIN_MARKERS):
        raise WeReadError("WeRead Web login is required at weread.qq.com", code="WEB_LOGIN_REQUIRED")
    parser = ContentFragment()
    parser.feed(html)
    candidates = []
    if parser.found:
        candidates.append("".join(parser.parts))
    encoded = CONTENT_NOENCODE.search(html)
    if encoded:
        try:
            candidates.append(json.loads(encoded.group(1)))
        except ValueError as exc:
            raise WeReadError("WeRead Web returned invalid article HTML", code="WEB_CONTENT_INSUFFICIENT") from exc
    if not candidates and not re.search(r"<(?:html|head|body)\b", html, flags=re.I):
        # /web/mp/content can return just the article HTML fragment.
        candidates.append(html)
    bodies = [article_text(candidate) for candidate in candidates]
    body = max(bodies, key=lambda text: len(re.sub(r"\s+", "", text)), default="")
    if len(re.sub(r"\s+", "", body)) < MIN_BODY_CHARACTERS:
        raise WeReadError("WeRead Web returned no identifiable full article body", code="WEB_CONTENT_INSUFFICIENT")
    return body


def store_cookie(path=DEFAULT_COOKIE_FILE, prompt=getpass):
    """Persist a user-supplied Web Cookie privately, without echo or logging it."""
    path = Path(path).expanduser()
    if PROJECT_ROOT in path.resolve().parents:
        raise WeReadError("Save the Web cookie outside the project directory", code="WEB_COOKIE_PERMISSIONS")
    if prompt is getpass and not sys.stdin.isatty():
        raise WeReadError("Run web-cookie in a local interactive terminal", code="WEB_COOKIE_INVALID")
    value = prompt("Paste the weread.qq.com Cookie header value (hidden): ")
    try:
        encoded = value.strip().encode("ascii")
    except (UnicodeError, AttributeError) as exc:
        raise WeReadError("Invalid WeRead Web cookie", code="WEB_COOKIE_INVALID") from exc
    if not encoded or len(encoded) > MAX_COOKIE_BYTES or b"\r" in encoded or b"\n" in encoded or b"=" not in encoded:
        raise WeReadError("Invalid WeRead Web cookie", code="WEB_COOKIE_INVALID")
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise WeReadError("Web cookie destination must be an owner-only regular file", code="WEB_COOKIE_PERMISSIONS")
            os.fchmod(fd, 0o600)
            os.write(fd, encoded)
        finally:
            os.close(fd)
    except OSError as exc:
        raise WeReadError("Cannot save private WeRead Web cookie file", code="WEB_COOKIE_INVALID") from exc
    return path


class WeReadWebBody:
    def __init__(self, cookie_file, opener=None):
        self.cookie_file = Path(cookie_file).expanduser()
        if PROJECT_ROOT in self.cookie_file.resolve().parents:
            raise WeReadError("Read the Web cookie from outside the project directory", code="WEB_COOKIE_PERMISSIONS")
        self.opener = opener or urllib.request.build_opener(NoRedirect)

    def _cookie(self):
        try:
            fd = os.open(self.cookie_file, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise WeReadError("WeRead Web cookie file must be an owner-only regular file (chmod 600)", code="WEB_COOKIE_PERMISSIONS")
                if info.st_size > MAX_COOKIE_BYTES:
                    raise WeReadError("WeRead Web cookie file is too large", code="WEB_COOKIE_INVALID")
                cookie = os.read(fd, MAX_COOKIE_BYTES + 1).decode("ascii").strip()
            finally:
                os.close(fd)
        except (OSError, UnicodeError) as exc:
            raise WeReadError("Cannot read private WeRead Web cookie file", code="WEB_COOKIE_INVALID") from exc
        if not cookie or len(cookie) > MAX_COOKIE_BYTES or "\r" in cookie or "\n" in cookie or "=" not in cookie:
            raise WeReadError("Invalid WeRead Web cookie file", code="WEB_COOKIE_INVALID")
        return cookie

    def read(self, review_id, *, title=None, account_name=None, published_at=None):
        if not isinstance(review_id, str) or not REVIEW_ID.fullmatch(review_id):
            raise WeReadError("Cannot request Web body without a valid WeRead review ID", code="WEB_REVIEW_ID_INVALID")
        url = WEB_CONTENT_URL + "?" + urllib.parse.urlencode({"reviewId": review_id})
        request = urllib.request.Request(url, headers={
            "Accept": "text/html,application/json",
            "User-Agent": USER_AGENT,
            "Cookie": self._cookie(),
        })
        try:
            with self.opener.open(request, timeout=WEB_TIMEOUT_SECONDS) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise WeReadError("WeRead Web returned HTTP {}".format(exc.code), code="WEB_HTTP_ERROR", status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise WeReadError("WeRead Web network request failed", code="WEB_NETWORK_ERROR") from exc
        if len(body) > MAX_RESPONSE_BYTES:
            raise WeReadError("WeRead Web response exceeded the size limit", code="WEB_CONTENT_TOO_LARGE")
        html = body.decode("utf-8", "replace")
        try:
            payload = json.loads(html)
        except ValueError:
            payload = None
        if isinstance(payload, dict) and "errCode" in payload:
            code = payload["errCode"]
            if code == -2010:
                raise WeReadError("WeRead Web login expired or absent; sign in at weread.qq.com", code="WEB_LOGIN_REQUIRED")
            raise WeReadError("WeRead Web rejected the article request (code {})".format(code), code="WEB_API_ERROR")
        return {
            "title": title, "accountName": account_name, "publishedAt": published_at,
            "markdown": extract_body(html), "contentSource": "微信读书网页（已授权会话）",
        }
