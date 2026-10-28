"""Use a catalogued public RSS feed only for the exact WeChat article URL.

The catalog and feed are allowlisted by download_rss. Never substitute another
article merely because its title or account resembles the requested one.
"""

from urllib.parse import parse_qs, urlsplit

from download_rss import RSSError, article_text, read_feed, resolve_feed
from weread_client import article_url

MIN_RSS_BODY_CHARACTERS = 80
ARTICLE_QUERY_KEYS = ("__biz", "mid", "idx", "sn")


def article_identity(url):
    if not article_url(url):
        return None
    parsed = urlsplit(url)
    if parsed.path.startswith("/s/"):
        return ("short", parsed.path) if parsed.path != "/s/" else None
    params = parse_qs(parsed.query)
    if all(len(params.get(key, [])) == 1 for key in ARTICLE_QUERY_KEYS):
        return ("query", *(params[key][0] for key in ARTICLE_QUERY_KEYS))
    return None  # Incomplete query parameters cannot identify a unique article.


class RSSFallback:
    def __init__(self, resolve=resolve_feed, read=read_feed):
        self.resolve = resolve
        self.read = read
        self.cache = {}

    def fetch(self, url, account_name):
        if not account_name:
            raise RSSError("RSS fallback needs a verified public-account name; pass --rss-account")
        identity = article_identity(url)
        if identity is None:
            raise RSSError("RSS fallback only accepts a public WeChat article URL")
        key = account_name.casefold()
        if key not in self.cache:
            try:
                self.cache[key] = self.read(self.resolve(account_name))
            except RSSError as exc:
                self.cache[key] = exc  # Avoid repeatedly querying a failing feed in one batch.
        feed = self.cache[key]
        if isinstance(feed, RSSError):
            raise RSSError(str(feed))
        feed_name, items = feed
        for item in items:
            if article_identity(item["url"]) != identity:
                continue
            body = article_text(item["html"])
            if len(body) < MIN_RSS_BODY_CHARACTERS:
                raise RSSError("RSS has this article, but content:encoded is absent or too short")
            return {
                "title": item["title"], "accountName": feed_name,
                "publishedAt": item["published"], "markdown": body,
                "contentSource": "公开 RSS（第三方正文，未与微信原文逐字核对）",
            }
        raise RSSError("RSS feed has no item matching this exact article URL")
