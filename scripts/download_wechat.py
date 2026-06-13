#!/usr/bin/env python3
"""
Download WeChat official account (公众号) articles via wechat-download-api.

Usage:
  python3 download_wechat.py status                    # Check if API is healthy
  python3 download_wechat.py search "name"             # Search for an account
  python3 download_wechat.py list <fakeid> [begin] [n] # List articles
  python3 download_wechat.py download <fakeid> [count] [output_dir]  # Download all
  python3 download_wechat.py rss <fakeid>              # Print RSS feed URL
"""

import requests
import json
import os
import sys
import re
import time

API = os.environ.get("WECHAT_API_URL", "http://localhost:8765")
DEFAULT_OUTPUT = os.path.join(os.getcwd(), "wechat_downloads")
MIN_DELAY = 3.2  # seconds between article requests (API rate limit)


# --------------- helpers ---------------

def _check_health():
    try:
        resp = requests.get(f"{API}/api/health", timeout=5)
        data = resp.json()
        return data.get("status") == "healthy"
    except Exception:
        return False


def _sanitize(title):
    """Turn an article title into a safe filename."""
    name = re.sub(r'[\\/:*?"<>|]', "", title)
    name = re.sub(r"\s+", "_", name)
    return name[:80]


# --------------- commands ---------------

def search_biz(query):
    """Search for official accounts by name."""
    resp = requests.get(f"{API}/api/public/searchbiz", params={"query": query})
    data = resp.json()
    if not data.get("success"):
        print(f"Search failed: {data.get('error', 'unknown error')}")
        return []
    biz_list = data.get("data", {}).get("list", [])
    for i, biz in enumerate(biz_list):
        print(f"[{i}] {biz['nickname']}  (alias: {biz.get('alias', 'N/A')})")
        print(f"    fakeid: {biz['fakeid']}")
    return biz_list


def list_articles(fakeid, begin=0, count=50, keyword=None):
    """List articles for a given fakeid."""
    params = {"fakeid": fakeid, "begin": begin, "count": count}
    if keyword:
        params["keyword"] = keyword
    resp = requests.get(f"{API}/api/public/articles", params=params)
    data = resp.json()
    if not data.get("success"):
        print(f"Failed: {data.get('error', 'unknown error')}")
        return []
    articles = data.get("data", {}).get("articles", [])
    total = data.get("data", {}).get("total", 0)
    print(f"Total: {total}  (showing {begin}-{begin+len(articles)-1})")
    for i, a in enumerate(articles):
        print(f"  [{begin+i}] {a.get('title', 'untitled')[:60]}")
    return articles


def _fetch_article(url):
    """Fetch a single article. Returns (content, error_msg)."""
    resp = requests.post(f"{API}/api/article", json={"url": url}, timeout=60)
    item = resp.json()
    if not item.get("success"):
        return None, item.get("error", "unknown")
    d = item["data"]
    content = d.get("plain_content") or d.get("content", "")
    if not content:
        return None, "empty content"
    return d, None


def download_all(fakeid, count=200, output_dir=None):
    """Download all articles for a fakeid, with resume and rate-limit handling."""
    out = output_dir or DEFAULT_OUTPUT
    os.makedirs(out, exist_ok=True)

    # --- 1. Fetch article list ---
    print("Fetching article list...")
    all_articles = []
    begin = 0
    while begin < count:
        params = {"fakeid": fakeid, "begin": begin, "count": min(50, count - begin)}
        resp = requests.get(f"{API}/api/public/articles", params=params)
        data = resp.json()
        if not data.get("success"):
            print(f"  Error: {data.get('error')}")
            break
        batch = data["data"]["articles"]
        if not batch:
            break
        all_articles.extend(batch)
        print(f"  {len(all_articles)} articles...", end="\r")
        if len(all_articles) >= data["data"]["total"]:
            break
        begin += len(batch)
        time.sleep(0.5)

    total = len(all_articles)
    print(f"\n{total} articles total. Downloading content...\n")

    # --- 2. Download articles with resume ---
    success = 0
    skipped, failures = 0, []
    delay = MIN_DELAY

    for i, a in enumerate(all_articles):
        title = a.get("title", "untitled")
        url = a.get("link", "")  # NOTE: field is "link", NOT "url"!
        if not url:
            failures.append((title, "no link field"))
            continue

        # Use aid as primary key to avoid collisions from duplicate/short titles
        aid = a.get("aid", "").replace("_", "-") or str(i)
        slug = _sanitize(title)
        fname = f"{aid}_{slug}"[:120]
        fpath = os.path.join(out, f"{fname}.txt")
        if os.path.exists(fpath) and os.path.getsize(fpath) > 100:
            skipped += 1
            continue

        print(f"[{i+1}/{total}] {title[:60]} ...", end=" ", flush=True)

        for attempt in range(3):
            try:
                d, err = _fetch_article(url)
                if d:
                    content = d.get("plain_content") or d.get("content", "")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(f"title: {title}\n")
                        f.write(f"author: {d.get('author', '')}\n")
                        f.write(f"published: {a.get('update_time', '')}\n")
                        f.write(f"url: {url}\n")
                        f.write("=" * 60 + "\n\n")
                        f.write(content)
                    success += 1
                    print(f"✓ {len(content)} chars")
                    delay = MIN_DELAY  # reset delay on success
                    time.sleep(delay)
                    break  # out of retry loop

                # Handle error
                if err and ("Rate limited" in err or "过于频繁" in err):
                    m = re.search(r"(\d+)秒", err)
                    wait = int(m.group(1)) + 1 if m else int(delay) + 3
                    if attempt < 2:
                        print(f"⏳ wait {wait}s...")
                        time.sleep(wait)
                        delay += 1
                        continue
                # Non-retryable or exhausted retries
                msg = err[:40] if err else "unknown"
                print(f"✗ {msg}")
                failures.append((title, err or "unknown"))
                time.sleep(delay)
                break

            except Exception as e:
                if attempt < 2:
                    print(f"⚠ retry...")
                    time.sleep(5)
                    continue
                print(f"✗ {e}")
                failures.append((title, str(e)))
                time.sleep(delay)
                break

    # --- 3. Report ---
    print(f"\n{'='*60}")
    print(f"Done.  Success: {success}  Skipped: {skipped}  Failed: {len(failures)}")
    if failures:
        # save failures for later inspection
        fail_path = os.path.join(out, "failures.json")
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(failures, f, ensure_ascii=False, indent=2)
        print(f"Failures saved to: {fail_path}")
    total_size = sum(
        os.path.getsize(os.path.join(out, x))
        for x in os.listdir(out)
        if x.endswith(".txt")
    )
    print(f"Total size: {total_size/1024:.0f} KB ({total_size/1024/1024:.2f} MB)")
    print(f"Output: {out}")


# --------------- cli ---------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]

    if cmd == "status":
        data = requests.get(f"{API}/api/health", timeout=5).json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python3 download_wechat.py search <keyword>")
            return
        search_biz(sys.argv[2])
    elif cmd == "list":
        if len(sys.argv) < 3:
            print("Usage: python3 download_wechat.py list <fakeid> [begin] [count]")
            return
        fakeid = sys.argv[2]
        begin = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 50
        list_articles(fakeid, begin, count)
    elif cmd == "download":
        if len(sys.argv) < 3:
            print("Usage: python3 download_wechat.py download <fakeid> [count] [output_dir]")
            return
        fakeid = sys.argv[2]
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 200
        out = sys.argv[4] if len(sys.argv) > 4 else None
        download_all(fakeid, count, out)
    elif cmd == "rss":
        if len(sys.argv) < 3:
            print("Usage: python3 download_wechat.py rss <fakeid>")
            return
        fakeid = sys.argv[2]
        print(f"RSS feed: {API}/api/rss/{fakeid}")
        print("Add this URL to Feedly / Inoreader / FreshRSS / NetNewsWire")
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()