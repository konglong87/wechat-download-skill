"""Identify a public account from a user-provided, accessible WeChat article.

This is a public-page read, not a WeRead search, CAPTCHA handler, or session API.
Only the page's visible account name and numeric base64 biz are accepted.
"""

import base64
import re
import urllib.error
import urllib.parse
import urllib.request

from public_page_identity import PageIdentity
from wechat_page_body import EINK_SOURCE_USER_AGENT, MAX_SOURCE_BYTES, NoRedirect, SOURCE_TIMEOUT_SECONDS
from weread_client import WeReadError, article_url

BIZ_ASSIGNMENT = re.compile(r"\bvar\s+(?:biz|__biz)\s*=\s*['\"]([A-Za-z0-9+/=]{8,80})['\"]")
NUMERIC_ID = re.compile(r"[0-9]{7,20}\Z")



def identify_html(page, *, expected_name=None):
    parser = PageIdentity()
    parser.feed(page)
    name = parser.fields.get("js_name")
    title = parser.fields.get("activity-name")
    if not name or not title:
        raise WeReadError("Public page did not expose a verifiable account name and title", code="ACCOUNT_IDENTITY_MISSING")
    if expected_name and name != expected_name:
        raise WeReadError("Public page account name does not match the expected account", code="ACCOUNT_IDENTITY_MISMATCH")
    numeric_ids = set()
    for candidate in BIZ_ASSIGNMENT.findall("\n".join(parser.scripts)):
        try:
            decoded = base64.b64decode(candidate + "=" * (-len(candidate) % 4), validate=True).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            continue
        if NUMERIC_ID.fullmatch(decoded):
            numeric_ids.add(decoded)
    if len(numeric_ids) != 1:
        raise WeReadError("Public page has no unique numeric biz identity", code="ACCOUNT_BIZ_UNAVAILABLE")
    return {"accountName": name, "accountId": "MP_WXS_" + numeric_ids.pop(), "articleTitle": title}


def identify_url(url, *, expected_name=None, opener=None):
    if not article_url(url):
        raise WeReadError("Expected an HTTPS WeChat article URL", code="SOURCE_URL_INVALID")
    opener = opener or urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(url, headers={"Accept": "text/html,application/xhtml+xml",
                                                    "User-Agent": EINK_SOURCE_USER_AGENT})
    try:
        with opener.open(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
            actual = urllib.parse.urlsplit(response.url)
            if response.url != url or actual.scheme != "https" or actual.hostname != "mp.weixin.qq.com" or (
                    actual.path != "/s" and not actual.path.startswith("/s/")):
                raise WeReadError("Public article was replaced by a verification page", code="SOURCE_WECHAT_CHALLENGE")
            data = response.read(MAX_SOURCE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise WeReadError("Public article returned HTTP {}".format(exc.code), code="SOURCE_HTTP_ERROR") from exc
    except urllib.error.URLError as exc:
        raise WeReadError("Public article could not be read", code="SOURCE_NETWORK_ERROR") from exc
    if len(data) > MAX_SOURCE_BYTES:
        raise WeReadError("Public article exceeds the size limit", code="SOURCE_TOO_LARGE")
    return identify_html(data.decode("utf-8", "replace"), expected_name=expected_name)
