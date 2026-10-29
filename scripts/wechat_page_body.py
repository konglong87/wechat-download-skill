"""Read a genuinely visible WeChat article body from its public page.

The pinned WeRead CLI already requests these original URLs with the eInk user
agent. This adapter retries that same public source only when the CLI discards a
real article because it scans challenge words across the *entire* HTML page.
It never follows verification redirects or treats a metadata preview as text.
"""

import ast
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import re
import urllib.error
import urllib.parse
import urllib.request

from download_rss import article_text
from weread_client import WeReadError, article_url
from weread_web_body import ContentFragment
from wechat_picture_body import download_picture_post

# Keep aligned with weread-omni@0.1.2's public eInk device identity.
EINK_SOURCE_USER_AGENT = "WeRead/2.1.2 WRBrand/Onyx wr_eink Dalvik/2.1.0 (Linux; U; Android 11; BOOX Build/onyx)"
MAX_SOURCE_BYTES = 10 * 1024 * 1024
SOURCE_TIMEOUT_SECONDS = 20
MIN_FULL_BODY_CHARACTERS = 500
CHALLENGE_PATH = "/mp/wappoc_appmsgcaptcha"
NOENCODE_PROPERTY = re.compile(r"\bcontent_noencode\s*:\s*([\'\"])")
PUBLIC_TITLE_PROPERTY = "og:title"
MAX_PUBLIC_TITLE_CHARACTERS = 300
PUBLIC_CREATE_TIME = re.compile(r"\bcreate_time:\s*['\"](\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)['\"]")


class PublicArticleMetadata(HTMLParser):
    """Read only the original page's declared Open Graph title."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or self.title:
            return
        attributes = dict(attrs)
        if attributes.get("property") != PUBLIC_TITLE_PROPERTY:
            return
        title = (attributes.get("content") or "").strip()
        if 0 < len(title) <= MAX_PUBLIC_TITLE_CHARACTERS:
            self.title = title


def extract_public_metadata(page):
    """Metadata accompanies a validated body/gallery; it is never success alone."""
    parser = PublicArticleMetadata()
    parser.feed(page)
    match = PUBLIC_CREATE_TIME.search(page)
    published_at = match.group(1) if match else None
    if published_at:
        try:
            datetime.fromisoformat(published_at)
        except ValueError:
            published_at = None
    return parser.title, published_at


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme == "https" and target.hostname == "mp.weixin.qq.com" and target.path == CHALLENGE_PATH:
            raise WeReadError("WeChat redirected to verification; stop rather than bypass it", code="SOURCE_WECHAT_CHALLENGE")
        raise WeReadError("WeChat article redirected; refusing to fetch another page", code="SOURCE_REDIRECT")


def _javascript_content_noencode(page):
    """Decode only a quoted JS string literal; never evaluate page JavaScript."""
    match = NOENCODE_PROPERTY.search(page)
    if not match:
        return None
    quote, start = match.group(1), match.end() - 1
    escaped = False
    for end in range(start + 1, len(page)):
        char = page[end]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            try:
                value = ast.literal_eval(page[start:end + 1])
            except (SyntaxError, ValueError, UnicodeError):
                return None
            return value if isinstance(value, str) else None
    return None


def extract_visible_body(page, *, title=None, preview=None):
    """Read an article container or long JS body, never a short teaser/shell."""
    if title and title not in unescape(page):
        raise WeReadError("Original page title does not match the requested article", code="SOURCE_IDENTITY_MISMATCH")
    parser = ContentFragment()
    parser.feed(page)
    candidates = []
    if parser.found:
        candidates.append("".join(parser.parts))
    encoded = _javascript_content_noencode(page)
    if encoded:
        candidates.append(encoded)
    teaser = re.sub(r"\s+", "", article_text(preview or ""))
    bodies = [article_text(candidate) for candidate in candidates]
    body = max(bodies, key=lambda text: len(re.sub(r"\s+", "", text)), default="")
    length = len(re.sub(r"\s+", "", body))
    if length < MIN_FULL_BODY_CHARACTERS or (teaser and length <= len(teaser)):
        raise WeReadError("Original page has no verified full body; only metadata or preview", code="SOURCE_CONTENT_INSUFFICIENT")
    return body


class WeChatPageBody:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener(NoRedirect)

    def read(self, url, *, title=None, account_name=None, published_at=None, preview=None, review_id=None):
        if not article_url(url):
            raise WeReadError("Expected an HTTPS WeChat article URL", code="SOURCE_URL_INVALID")
        request = urllib.request.Request(url, headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": EINK_SOURCE_USER_AGENT,
        })
        try:
            with self.opener.open(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
                if urllib.parse.urlsplit(response.url).path not in ("/s",) and not urllib.parse.urlsplit(response.url).path.startswith("/s/"):
                    raise WeReadError("Original page was replaced by a verification or error page", code="SOURCE_WECHAT_CHALLENGE")
                page = response.read(MAX_SOURCE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise WeReadError("WeChat original returned HTTP {}".format(exc.code), code="SOURCE_HTTP_ERROR", status=exc.code) from exc
        except urllib.error.URLError as exc:
            raise WeReadError("WeChat original request failed", code="SOURCE_NETWORK_ERROR") from exc
        if len(page) > MAX_SOURCE_BYTES:
            raise WeReadError("WeChat original exceeds the body size limit", code="SOURCE_TOO_LARGE")
        html = page.decode("utf-8", "replace")
        page_title, page_published_at = extract_public_metadata(html)
        if title and page_title and re.sub(r"\s+", "", title) != re.sub(r"\s+", "", page_title):
            raise WeReadError("Original page title does not match the requested article", code="SOURCE_IDENTITY_MISMATCH")
        title = title or page_title
        published_at = published_at or page_published_at
        try:
            markdown = extract_visible_body(html, title=title, preview=preview)
        except WeReadError as exc:
            if exc.code != "SOURCE_CONTENT_INSUFFICIENT":
                raise
            gallery = download_picture_post(
                html, opener=self.opener, user_agent=EINK_SOURCE_USER_AGENT,
                source_url=url, title=title, account_name=account_name,
                published_at=published_at, preview=preview or _javascript_content_noencode(html),
                review_id=review_id,
            )
            if gallery is None:
                raise
            return gallery
        return {
            "reviewId": review_id, "title": title, "accountName": account_name,
            "publishedAt": published_at, "markdown": markdown,
            "contentSource": "微信原文公开页（验证可见正文；非全文一致性保证）",
        }
