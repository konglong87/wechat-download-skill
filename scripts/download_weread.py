#!/usr/bin/env python3
"""Download WeChat articles through an authenticated WeRead account.

Examples:
  python3 scripts/download_weread.py login
  python3 scripts/download_weread.py search 人民日报
  python3 scripts/download_weread.py list MP_WXS_1234567890 0 10
  python3 scripts/download_weread.py download MP_WXS_1234567890 200 ./articles
  python3 scripts/download_weread.py url https://mp.weixin.qq.com/s/ARTICLE ./articles
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from article_retrieval import read_article
from rss_fallback import RSSFallback
from weread_client import WeReadClient, WeReadError, article_url

PAGE_SIZE = 20
MAX_ARTICLES = 1000
PAGE_DELAY_SECONDS = 1.0
ARTICLE_DELAY_SECONDS = 3.2
DEFAULT_OUTPUT = Path.cwd() / "wechat_downloads"
FILENAME_CHARACTERS = 55
FAILURES_FILENAME = "failures.json"


def _slug(value):
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", value or "untitled")
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return (text or "untitled")[:FILENAME_CHARACTERS]


def _entry_title(entry, fallback):
    mp_info = entry.get("mpInfo")
    return str(entry.get("title") or (mp_info.get("title") if isinstance(mp_info, dict) else None) or fallback)


def _existing_article(output_dir, digest):
    return next(
        (p for p in output_dir.glob(digest + "_*.md") if p.stat().st_size > 100),
        None,
    )


def _save_article(output_dir, key, title, url, entry, result):
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    existing = _existing_article(output_dir, digest)
    if existing:
        return existing, False
    markdown = result.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise WeReadError("Article returned without Markdown; cannot save as a readable archive")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (digest + "_" + _slug(result.get("title") or title) + ".md")
    metadata = [
        "# " + str(result.get("title") or title or "untitled"),
        "",
        "> 来源：" + url,
        "> 公众号：" + str(result.get("accountName") or ""),
        "> 发布时间：" + str(result.get("publishedAt") or entry.get("createTime") or ""),
        *(["> 内容渠道：" + result["contentSource"]] if result.get("contentSource") else []),
        "",
        "---",
        "",
    ]
    path.write_text("\n".join(metadata) + markdown + "\n", encoding="utf-8")
    if path.stat().st_size <= 100:
        path.unlink()
        raise WeReadError("Saved article is unexpectedly short")
    return path, True


def iter_articles(client, account_id, count, sleep=time.sleep):
    """Stream pages so completed downloads survive later paging failures."""
    if not 1 <= count <= MAX_ARTICLES:
        raise WeReadError("Article count must be between 1 and {}".format(MAX_ARTICLES))
    offset, seen, yielded = None, set(), 0
    while yielded < count:
        page = client.articles(account_id, min(PAGE_SIZE, count - yielded), offset)
        entries = page["articles"]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = entry.get("reviewId")
            if not isinstance(key, str) or not key or key in seen:
                continue
            seen.add(key)
            yielded += 1
            yield entry
            if yielded == count:
                break
        if yielded >= count or not entries:
            break
        next_offset = page.get("nextOffset")
        if not isinstance(next_offset, int):
            break
        if next_offset <= (offset if offset is not None else 0):
            raise WeReadError("Article pagination did not advance")
        offset = next_offset
        sleep(PAGE_DELAY_SECONDS)
    if not yielded:
        raise WeReadError("No articles returned; verify the WeRead account ID and login")


def collect_articles(client, account_id, count, sleep=time.sleep):
    return list(iter_articles(client, account_id, count, sleep=sleep))


def download_account(client, account_id, count=200, output_dir=DEFAULT_OUTPUT, sleep=time.sleep,
                     rss_account=None, rss_fallback=None):
    output_dir = Path(output_dir)
    fallback = rss_fallback if rss_fallback is not None else RSSFallback()
    success = skipped = processed = 0
    failures = []
    try:
        for processed, entry in enumerate(iter_articles(client, account_id, count, sleep=sleep), 1):
            key = entry["reviewId"]
            title = _entry_title(entry, key)
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
            if _existing_article(output_dir, digest):
                skipped += 1
                continue
            try:
                url = client.resolve_url(entry)
                if not url:
                    raise WeReadError("WeRead did not provide a valid original article URL")
                result = read_article(client, url, account_name=rss_account, fallback=fallback, sleep=sleep)
                path, saved = _save_article(output_dir, key, title, url, entry, result)
                success += int(saved)
                skipped += int(not saved)
                print("[{}/{}] {} -> {}".format(processed, count, title[:50], path.name))
            except WeReadError as exc:
                failures.append({"reviewId": key, "title": title, "error": str(exc)})
                print("[{}/{}] FAILED {}: {}".format(processed, count, title[:50], exc), file=sys.stderr)
                if any(x in str(exc).lower() for x in ("freq control", "rate limit", "-2041", "验证", "登录")):
                    break  # Do not hammer a rate-limited or challenged account.
            if processed < count:
                sleep(ARTICLE_DELAY_SECONDS)
    except WeReadError as exc:
        if not processed:
            raise
        failures.append({"accountId": account_id, "error": "Article list: {}".format(exc)})
        print("List stopped after {} items: {}".format(processed, exc), file=sys.stderr)
    failure_path = output_dir / FAILURES_FILENAME
    if failures:
        output_dir.mkdir(parents=True, exist_ok=True)
        failure_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    elif failure_path.is_file():
        failure_path.unlink()  # A successful retry must not leave a stale failure report.
    print("Downloaded: {}  Skipped: {}  Failed: {}  Listed: {}  Output: {}".format(
        success, skipped, len(failures), processed, output_dir
    ))
    return 1 if failures else 0


def download_url(client, url, output_dir=DEFAULT_OUTPUT, rss_account=None, rss_fallback=None,
                 sleep=time.sleep):
    if not article_url(url):
        raise WeReadError("Expected an https://mp.weixin.qq.com/s article URL")
    output_dir = Path(output_dir)
    result = read_article(client, url, account_name=rss_account, fallback=rss_fallback, sleep=sleep)
    path, saved = _save_article(output_dir, url, result.get("title"), url, {}, result)
    print("{}: {} ({} bytes)".format("Downloaded" if saved else "Already exists", path, path.stat().st_size))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="refetch articles instead of using cached content")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="scan a WeRead QR code (separate from MP login)")
    commands.add_parser("status", help="verify WeRead authentication")
    search = commands.add_parser("search", help="search public accounts")
    search.add_argument("query")
    listing = commands.add_parser("list", help="list a public account's articles")
    listing.add_argument("account_id")
    listing.add_argument("begin", nargs="?", type=int, default=0)
    listing.add_argument("count", nargs="?", type=int, default=20)
    download = commands.add_parser("download", help="download public account articles as Markdown")
    download.add_argument("account_id")
    download.add_argument("count", nargs="?", type=int, default=200)
    download.add_argument("output_dir", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    download.add_argument("--rss-account", help="exact public-account name if WeRead cannot identify it")
    direct = commands.add_parser("url", help="download a known article URL")
    direct.add_argument("article_url")
    direct.add_argument("output_dir", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    direct.add_argument("--rss-account", help="exact public-account name if WeRead cannot identify it")
    args = parser.parse_args(argv)
    try:
        client = WeReadClient(refresh=args.refresh)
        if args.command == "login":
            return subprocess.call(client.command("login"))
        if args.command == "status":
            result = client.call("doctor")
        elif args.command == "search":
            result = client.search(args.query)
        elif args.command == "list":
            result = client.articles(args.account_id, args.count, args.begin or None)
        elif args.command == "download":
            return download_account(client, args.account_id, args.count, args.output_dir, rss_account=args.rss_account)
        else:
            return download_url(client, args.article_url, args.output_dir, rss_account=args.rss_account)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except WeReadError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
