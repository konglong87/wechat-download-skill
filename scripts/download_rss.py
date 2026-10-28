#!/usr/bin/env python3
"""Download recent public WeChat articles from a catalogued RSS feed.

The RSS backend needs no login, but covers only the public feeds and items the
provider currently exposes. It never bypasses WeChat verification pages.
"""

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from weread_client import article_url

CATALOG_URL = "https://wechat2rss.xlab.app/list/all"
FEED_HOST = "wechat2rss.xlab.app"
FEED_PATH = re.compile(r"^/feed/[a-f0-9]{40}\.xml$")
USER_AGENT = "wechat-download-skill/1.2 (+personal RSS archival)"
CONTENT_TAG = "{http://purl.org/rss/1.0/modules/content/}encoded"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_FEED_ITEMS = 100
DEFAULT_OUTPUT = Path.cwd() / "wechat_downloads"


class RSSError(RuntimeError):
    pass


def validated_feed_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != FEED_HOST or parsed.port or parsed.username or parsed.password):
            return None
    except ValueError:
        return None
    if parsed.query or parsed.fragment or not FEED_PATH.fullmatch(parsed.path):
        return None
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RSSError("RSS source redirected; refusing to fetch another destination")


def _fetch(url):
    if url != CATALOG_URL and not validated_feed_url(url):
        raise RSSError("Only the public catalog and its HTTPS feed URLs are allowed")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html, application/rss+xml, application/xml"})
    opener = urllib.request.build_opener(NoRedirect)
    for attempt in range(2):
        try:
            with opener.open(request, timeout=20) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except urllib.error.HTTPError as exc:
            # Do not retry authorization or rate-limit refusals.
            if exc.code not in (502, 503, 504) or attempt:
                raise RSSError("RSS request failed: HTTP {}".format(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt:
                raise RSSError("RSS request failed: {}".format(exc)) from exc
        time.sleep(2)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RSSError("RSS response exceeds the size limit")
    return body


class CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.accounts = []
        self.current_url = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            url = dict(attrs).get("href", "")
            self.current_url = validated_feed_url(urllib.parse.urljoin(CATALOG_URL, url))
            self.current_text = []

    def handle_data(self, data):
        if self.current_url:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_url:
            name = " ".join(" ".join(self.current_text).split())
            if name:
                self.accounts.append({"name": name, "feed": self.current_url})
            self.current_url = None
            self.current_text = []


def search_accounts(keyword):
    parser = CatalogParser()
    parser.feed(_fetch(CATALOG_URL).decode("utf-8", "replace"))
    matches = [x for x in parser.accounts if keyword.casefold() in x["name"].casefold()]
    return matches


def resolve_feed(name_or_url):
    valid = validated_feed_url(name_or_url)
    if valid:
        return valid
    candidates = search_accounts(name_or_url)
    exact = [x for x in candidates if x["name"].casefold() == name_or_url.casefold()]
    if len(exact) == 1:
        return exact[0]["feed"]
    if not candidates:
        raise RSSError("Account not in the public RSS catalog; use the WeRead backend instead")
    raise RSSError("Ambiguous account name; choose one exact name or feed URL: {}".format(
        ", ".join(x["name"] for x in candidates[:8])
    ))


def read_feed(url):
    valid = validated_feed_url(url)
    if not valid:
        raise RSSError("Expected a catalogued HTTPS feed URL")
    raw = _fetch(valid)
    if b"<!DOCTYPE" in raw.upper():
        raise RSSError("RSS feed contains a prohibited DOCTYPE")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RSSError("RSS feed is not valid XML") from exc
    channel = root.find("channel")
    if channel is None:
        raise RSSError("RSS feed has no channel")
    items = []
    for item in channel.findall("item")[:MAX_FEED_ITEMS]:
        link = article_url(item.findtext("link"))
        if not link:
            continue
        items.append({
            "title": item.findtext("title") or "untitled",
            "url": link,
            "published": item.findtext("pubDate") or "",
            "html": item.findtext(CONTENT_TAG) or "",
        })
    return channel.findtext("title") or "unknown", items


class ArticleText(HTMLParser):
    BLOCK_TAGS = frozenset(("p", "br", "div", "section", "h1", "h2", "h3", "li", "blockquote"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored += 1
        elif tag == "img" and not self.ignored:
            source = dict(attrs).get("data-src") or dict(attrs).get("src")
            if source and source.startswith("https://"):
                self.parts.append("\n[图片] " + source + "\n")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.ignored:
            self.ignored -= 1
        elif tag in self.BLOCK_TAGS and not self.ignored:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def article_text(html):
    parser = ArticleText()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def download_feed(url, count=20, output_dir=DEFAULT_OUTPUT):
    if not 1 <= count <= MAX_FEED_ITEMS:
        raise RSSError("Request between 1 and {} recent RSS items".format(MAX_FEED_ITEMS))
    account, items = read_feed(url)
    if not items:
        raise RSSError("RSS returned no article links")
    output_dir = Path(output_dir)
    success = skipped = 0
    failures = []
    for item in items[:count]:
        digest = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()[:12]
        title = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", item["title"])[:55].strip(" ._") or "untitled"
        path = output_dir / (digest + "_" + title + ".txt")
        existing = next((p for p in output_dir.glob(digest + "_*.txt") if p.stat().st_size > 100), None)
        if existing:
            skipped += 1
            continue
        body = article_text(item["html"])
        if len(body) < 80:
            failures.append({"title": item["title"], "url": item["url"], "error": "RSS content:encoded missing or too short"})
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("title: {}\naccount: {}\npublished: {}\nurl: {}\n{}\n\n{}\n".format(
            item["title"], account, item["published"], item["url"], "=" * 60, body
        ), encoding="utf-8")
        success += 1
        print("Saved {} ({} bytes)".format(path.name, path.stat().st_size))
    if failures:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Account: {}  Available in feed: {}  Downloaded: {}  Skipped: {}  Failed: {}".format(
        account, len(items), success, skipped, len(failures)
    ))
    if count > len(items):
        print("Only {} recent items are present; requested {}. Not a full-history archive.".format(len(items), count), file=sys.stderr)
    return 1 if failures or count > len(items) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="search the public feed catalog")
    search.add_argument("keyword")
    listing = sub.add_parser("list", help="list recent feed items")
    listing.add_argument("account_or_feed")
    download = sub.add_parser("download", help="save feed-provided article text")
    download.add_argument("account_or_feed")
    download.add_argument("count", nargs="?", type=int, default=20)
    download.add_argument("output_dir", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            data = search_accounts(args.keyword)
            if not data:
                raise RSSError("No matching account in the public RSS catalog")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        feed = resolve_feed(args.account_or_feed)
        if args.command == "list":
            account, items = read_feed(feed)
            print(json.dumps({"account": account, "available": len(items), "articles": [
                {k: value for k, value in item.items() if k != "html"} for item in items
            ]}, ensure_ascii=False, indent=2))
            return 0 if items else 1
        return download_feed(feed, args.count, args.output_dir)
    except RSSError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
