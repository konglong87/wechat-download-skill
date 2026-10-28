# wechat-download-skill

An agent skill and CLI for discovering WeChat official accounts through a **QR-authenticated WeRead account** and saving readable article text as Markdown. Known article URLs can be downloaded directly. An optional separately authenticated WeRead Web body route can be tried when the public source is blocked; public RSS is a login-free fallback. The legacy WeChat MP admin route is retained only for compatibility.

> **Individual live tests (October 28, 2026):** Of the newest three 匿名测试公众号 posts, the second (Ontology) produced a **42,669-byte Markdown file with 17,671 body characters**; the first and third provided only previews: **1/3 full bodies**. A [previously successful article](https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE) also succeeded after a forced refresh. Individual and batch modes use the same body reader; splitting does not unlock otherwise inaccessible articles.

[中文说明](README.md)

## Install and sign in

On macOS or Linux, install Python **≥3.9**, Node.js **≥22.13.0**, and npm. You do not need WeChat MP administrator access; scan the QR code with a WeChat account that has WeRead.

```bash
git clone https://github.com/konglong87/wechat-download-skill.git
cd wechat-download-skill
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login   # scan and confirm on your phone
python3 scripts/download_weread.py status  # auth.status should be authenticated
```

The installer pins `weread-omni@0.1.2` under `~/.local/share/wechat-download-skill/weread-omni/`, without changing global npm packages. The upstream CLI owns the eInk session in your home directory. This skill does not read cookies by default; only an explicitly enabled Web route reads an owner-only Cookie file, and never prints or commits it. The phone's WeRead device list may show the new login as **BOOX**. WeRead authentication is separate from the WeChat MP admin session.

### Download a known article URL

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads
# Bypass the CLI cache and refetch:
python3 scripts/download_weread.py --refresh url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads
```

Replace the example with your own `https://mp.weixin.qq.com/s/...` article URL. On success, check the printed `.md` path and size, then inspect the body. The example was verified on a specific date; future availability is not guaranteed.

### Start with an account name

```bash
python3 scripts/download_weread.py search '匿名测试公众号'
# Replace this illustrative ID with bookInfo.bookId from the search result:
python3 scripts/download_weread.py list MP_WXS_1234567890 0 5
python3 scripts/download_weread.py download MP_WXS_1234567890 5 ./wechat_downloads
```

Test 1–5 articles and read the saved files before requesting more. The default request is 200 and the per-run maximum is 1,000, **not a promise of complete account history**. A WeRead `MP_WXS_<digits>` ID is not an MP admin `fakeid`. The skill never subscribes to an account without explicit user action.

## Output and limitations

- Each successful article becomes one Markdown file with the original URL, account, and publication time; existing files are skipped. Images are **not downloaded locally**; any retained image links remain remote.
- Empty bodies and pages containing only author/navigation controls are rejected. Batch failures go to `failures.json` with a nonzero exit code. Check both counts and actual file content: successful search or listing does not prove readable articles.
- Search/listing briefly returned `-2041` during live testing, then recovered without a separate phone verification prompt. Stop on rate limits and try later rather than bypassing challenges.
- Upstream may mark even a long result `completeness=unverified`. A plausible full body is not a byte-for-byte comparison to the original. Deleted, restricted, paid, or otherwise unavailable content may fail. Archive only content you may access and use.

## Bounded retries, visible public body, and exact-item RSS

- A missing/insufficient body, timeout, or transient service error gets **up to three retries after the initial request**, with **2/4/8-second backoff** and a forced CLI cache refresh. Explicit verification, rate limits, `-2041`, and blocked pages are **not** hammered. The previous `HEAD` redirect guard was removed: even an article that succeeds with a fresh WeRead CLI request returned a challenge to independent `HEAD`, so HEAD alone is not proof that a GET body is unavailable.
- After the eInk source fails, the adapter makes one bounded, no-redirect request to the public article URL with the pinned eInk user agent. It accepts only a substantive visible `#js_content` or long `content_noencode`, never a teaser. An explicitly configured Web session then gets one try before RSS. Finally the adapter uses the verified account name from its response, or an explicit `--rss-account 'Exact account name'`, to look up the public RSS catalogue. It saves a `.md` file only if the feed has the **same article URL identity** (short link or all `__biz`/`mid`/`idx`/`sn` fields) and a nontrivial `content:encoded` body. The Markdown records its third-party RSS provenance. A similar title or a neighboring article is never substituted.
- Missing catalogue entries, a slow feed, no exact article match, or a short RSS body remain failures with nonzero exit status and `failures.json` for batches. Search/list failures before an article URL is available cannot be matched to an exact RSS item; use the standalone RSS command after confirming the account.

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads --rss-account 'Exact account name'
```

Individual live retest on October 28, 2026: the upstream CLI scanned the entire HTML for “需要验证” and falsely rejected the second article, which itself discusses verification. Parsing the actual article container saved **42,669 bytes / 17,671 body characters**; the saved beginning, middle and end were nonempty and a fresh source read matched exactly. Articles 1 and 3 provided only 326/447-character previews and no visible full-body container; they were **not** saved. The public RSS catalogue did not include the account (and sometimes timed out). Actual result: **1/3**.


## Optional authenticated WeRead Web body (experimental)

The [we-mp-rss community implementation](https://github.com/rachelos/we-mp-rss/blob/main/core/wx/model/weread_mp.py) describes `https://weread.qq.com/web/mp/content?reviewId=...`. A WeRead **Web** login is separate from the already-authenticated `weread-omni` eInk account. The endpoint returned `errCode=-2010` (no user) without Web authorization. **No newest-three full-body success has been verified through an authorized Web session.** This undocumented interface may change.

1. Personally sign in at `https://weread.qq.com` in your browser and verify the target article is readable there. Never share a Cookie or verification code in a chat or Issue.
2. If you choose this route, select a same-origin `weread.qq.com` request in your browser's **Network** developer tools. Copy its **Request Headers → Cookie value** (not another site's Cookie). In your own interactive terminal, run `python3 scripts/download_weread.py web-cookie` and paste into the hidden prompt. The private `~/.local/share/wechat-download-skill/weread-web.cookie` file is mode `0600`; `*.cookie` is ignored by Git. Treat this file as a login secret.
3. Re-run the download below. The Cookie is sent only to the fixed WeRead Web content endpoint with no redirects; login/challenge shells and short bodies are rejected. If it fails, the exact-item RSS fallback still runs and the process exits nonzero if no body was saved.

```bash
python3 scripts/download_weread.py --refresh download MP_WXS_1234567890 3 ./wechat_downloads/匿名测试公众号 --rss-account '匿名测试公众号'
# Optional private-file override: --web-cookie-file /private/path/weread-web.cookie before "download"
```

Re-sign in and re-run `web-cookie` if the session expires; to disable the route, move the private file elsewhere yourself. Never bypass verification, rate limits, or paid access. Verify the three actual `.md` files before scheduling unattended downloads.

## Scheduled checks: article discovery, per-post body verification

An agent may periodically run `status`, `list ID 0 10`, then `download ID 10 ./wechat_downloads/account` in a **persistent** output directory, reporting newly saved Markdown files, skipped files, failures, and the process exit code. On a nonzero exit, do not report a successful check or “no new articles.” Choose a count large enough to cover new posts since the last run. Scheduling belongs to the user's Codex/Claude/other agent; this project does not install background jobs and saves a separate Web session secret only if the user explicitly invokes `web-cookie`.

**Individual retest on October 28, 2026: 1/3 newest 匿名测试公众号 bodies saved; two remained previews and the RSS catalogue did not include the account.** This can discover posts and archive readable full bodies, but **cannot promise unattended full text for every latest post**. Report the failed titles and nonzero exit status.

## Login-free RSS fallback

The primary article command tries the fallback automatically when it has an article URL and account name. To query an indexed feed independently, or to work without WeRead login:

```bash
python3 scripts/download_rss.py search '小众软件'
python3 scripts/download_rss.py list 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml'
python3 scripts/download_rss.py download 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml' 1 ./wechat_downloads
```

This route writes recent `content:encoded` bodies to `.txt` without requesting restricted WeChat article pages. A live test saved and read back an article on October 28, 2026; later requests to the same feed timed out or returned incomplete responses. The fallback covers only indexed accounts and currently available feed items; it is **not** a general-purpose URL downloader.

## Agent skill and maintenance

The scripts work directly in the cloned project. To use the Agent Skill, name the cloned directory `wechat-download` (matching [`SKILL.md`](SKILL.md)) and place it in your agent's skills directory; for Codex, `~/.codex/skills/wechat-download/` is one option. Set `WEREAD_CLI=/path/to/weread-omni` for a custom CLI or `WEREAD_ACCOUNT=alias` for another logged-in account.

```bash
python3 -m unittest discover -s tests -v
```

Architecture: `download_weread.py → weread_client.py → [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni) (MIT) → WeRead index and public article URLs`. The strict `wechat_page_body.py` extracts a genuinely visible public article body; optional `weread_web_body.py` uses only a user-authorized Web session; exact RSS is the final fallback. The legacy `download_wechat.py`/`start_wechat_api.sh` route is compatible with [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api), but its article-list endpoint returned `ret=200013, freq control` in live testing and is not the recommended batch route. No third-party source is copied; do not bypass verification or access controls.
