# wechat-download-skill

An agent skill and CLI for discovering WeChat official accounts through a **QR-authenticated WeRead account** and saving readable article text as Markdown. Known article URLs can be downloaded directly. An optional separately authenticated WeRead Web body route can be tried when the public source is blocked; public RSS is a login-free fallback. The legacy WeChat MP admin route is retained only for compatibility.

> **Live test (October 28, 2026):** A [user-provided article](https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE) was saved through WeRead as a 40,490-byte Markdown file with approximately 19,832 body characters. Its beginning, middle, and end were inspected. Other articles returned only page chrome or insufficient content. **Arbitrary accounts, every article, and complete historical archives are not guaranteed.** The adapter refuses obvious empty previews rather than reporting false success.

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

## Bounded retries and exact-item RSS fallback

- A missing/insufficient body, timeout, or transient service error gets **up to three retries after the initial request**, with **2/4/8-second backoff** and a forced CLI cache refresh. One bounded, no-redirect `HEAD` check detects a WeChat verification redirect and stops futile retries. Explicit verification, rate limits, `-2041`, and blocked pages are **not** hammered.
- After the eInk source fails, an explicitly configured Web session gets one try before RSS. Then the adapter uses the verified account name from its response, or an explicit `--rss-account 'Exact account name'`, to look up the public RSS catalogue. It saves a `.md` file only if the feed has the **same article URL identity** (short link or all `__biz`/`mid`/`idx`/`sn` fields) and a nontrivial `content:encoded` body. The Markdown records its third-party RSS provenance. A similar title or a neighboring article is never substituted.
- Missing catalogue entries, a slow feed, no exact article match, or a short RSS body remain failures with nonzero exit status and `failures.json` for batches. Search/list failures before an article URL is available cannot be matched to an exact RSS item; use the standalone RSS command after confirming the account.

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads --rss-account 'Exact account name'
```

A later live run on October 28, 2026 still saved **0/3** latest 匿名测试公众号 articles: posts 1 and 3 exhausted three backoff retries, post 2 was explicitly blocked and was not retried, and the account was not in the public RSS catalogue. Independent requests for all three original URLs redirected to WeChat verification; the new HEAD guard stops those wasted retries. The Web body endpoint returned `errCode=-2010` without a Web login and is not yet validated with an authorized session. A separate real RSS fallback test against an indexed account hit a TLS handshake timeout. The mechanism is implemented and covered by exact-match/retry tests, but availability of the third-party feed is not guaranteed.

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

## Scheduled checks: article discovery, not guaranteed full-text delivery

An agent may periodically run `status`, `list ID 0 10`, then `download ID 10 ./wechat_downloads/account` in a **persistent** output directory, reporting newly saved Markdown files, skipped files, failures, and the process exit code. On a nonzero exit, do not report a successful check or “no new articles.” Choose a count large enough to cover new posts since the last run. Scheduling belongs to the user's Codex/Claude/other agent; this project does not install background jobs and saves a separate Web session secret only if the user explicitly invokes `web-cookie`.

**Live test on October 28, 2026: the three newest indexed posts from 匿名测试公众号 were listed, but all three returned `SOURCE_CONTENT_INSUFFICIENT`; `0/3` new bodies were saved. The public RSS catalogue did not include that account.** This path can currently detect new article metadata, but **unattended delivery of the latest full text for that account is not established**. A different known URL from the same account was successfully downloaded; availability varies by article.

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

Architecture: `download_weread.py → weread_client.py → [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni) (MIT) → WeRead index and public article URLs`. The optional `weread_web_body.py` uses only a user-authorized Web session; RSS is an independent fallback. The legacy `download_wechat.py`/`start_wechat_api.sh` route is compatible with [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api), but its article-list endpoint returned `ret=200013, freq control` in live testing and is not the recommended batch route. No third-party source is copied; do not bypass verification or access controls.
