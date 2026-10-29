#!/usr/bin/env python3
"""Archive explicitly supplied public WeChat article URLs without WeRead login.

The URL list can be filled by WeChat's normal share action, a verified public
RSS feed, or another lawful source. This command does not discover new URLs.
"""

import argparse
from pathlib import Path
import sys
import time

from article_archive import _existing_article_for_url, _save_article
from wechat_page_body import PUBLIC_BROWSER_USER_AGENT, WeChatPageBody
from weread_client import WeReadError, article_url

MAX_BATCH_URLS = 100
BATCH_DELAY_SECONDS = 3.2
STOP_CODES = frozenset(("SOURCE_WECHAT_CHALLENGE", "SOURCE_REDIRECT", "SOURCE_HTTP_ERROR",
                        "ACCOUNT_IDENTITY_MISMATCH", "ACCOUNT_IDENTITY_MISSING"))
DEFAULT_OUTPUT = Path.cwd() / "wechat_downloads"


def load_links(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    links = []
    for number, raw in enumerate(lines, 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if not article_url(value):
            raise ValueError("Line {}: expected an HTTPS mp.weixin.qq.com/s article URL".format(number))
        if value not in links:
            links.append(value)
        if len(links) > MAX_BATCH_URLS:
            raise ValueError("Batch exceeds {} unique URLs".format(MAX_BATCH_URLS))
    if not links:
        raise ValueError("No article links in input file")
    return links


def download_links(links, output_dir, *, account=None, source=None, sleep=time.sleep):
    """Write only body-verified articles; preserve successes on later failures."""
    output_dir = Path(output_dir)
    source = source or WeChatPageBody(user_agent=PUBLIC_BROWSER_USER_AGENT, verify_account=True)
    downloaded = skipped = 0
    failed = []
    for index, url in enumerate(links, 1):
        existing = _existing_article_for_url(output_dir, url)
        if existing:
            if account and "> 公众号：" + account not in existing.read_text(encoding="utf-8").splitlines()[:8]:
                print("[{}/{}] FAILED {}: existing archive has a different or missing account; use another output directory".format(
                    index, len(links), url), file=sys.stderr)
                return 1
            skipped += 1
            print("[{}/{}] Already exists: {}".format(index, len(links), existing))
            continue
        if index > 1:
            sleep(BATCH_DELAY_SECONDS)
        try:
            result = source.read(url, account_name=account)
            path, saved = _save_article(output_dir, url, result.get("title"), url, {}, result)
        except WeReadError as exc:
            failed.append((url, exc))
            print("[{}/{}] FAILED {}: {}".format(index, len(links), url, exc), file=sys.stderr)
            if exc.code in STOP_CODES or exc.status in (403, 429):
                print("Stopped: access refusal or challenge; no automatic retry.", file=sys.stderr)
                break
        else:
            downloaded += int(saved)
            skipped += int(not saved)
            print("[{}/{}] {}: {} ({} bytes)".format(index, len(links),
                  "Downloaded" if saved else "Already exists", path, path.stat().st_size))
    print("Downloaded: {}  Skipped: {}  Failed: {}  Output: {}".format(
          downloaded, skipped, len(failed), output_dir))
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    single = commands.add_parser("url", help="archive one supplied original article URL")
    batch = commands.add_parser("batch", help="archive one original URL per line")
    single.add_argument("article_url")
    batch.add_argument("links_file", type=Path)
    for command in (single, batch):
        command.add_argument("output_dir", nargs="?", type=Path, default=DEFAULT_OUTPUT)
        command.add_argument("--account", help="exact visible public-account name to verify")
    args = parser.parse_args(argv)
    try:
        if args.command == "url":
            if not article_url(args.article_url):
                raise ValueError("Expected an HTTPS mp.weixin.qq.com/s article URL")
            links = [args.article_url]
        else:
            links = load_links(args.links_file)
        return download_links(links, args.output_dir, account=args.account)
    except (OSError, ValueError) as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
