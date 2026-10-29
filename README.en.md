# wechat-download-skill

An agent skill and CLI for discovering WeChat official accounts through a **QR-authenticated WeRead account** and saving normal article text as Markdown or image-post galleries as Markdown plus local original images. Known article URLs can be downloaded directly. An optional separately authenticated WeRead Web body route can be tried when the public source is blocked; public RSS is a login-free fallback. The legacy WeChat MP admin route is retained only for compatibility.

> **Latest-three real download (October 28, 2026):** All three newest 匿名测试公众号 posts were archived: the Ontology post is a normal **42,669-byte Markdown / 17,671-character body**; posts 1 and 3 are WeChat `item_show_type=8` image posts, archived with their captions and **7 + 8 original images**. Result: **3/3 post packages, 15/15 locally saved images**, with a successful batch recheck. Text inside images has **not** been OCRed; this is not three plain-text full articles.


[中文说明](README.md)

## Install and sign in

On macOS or Linux, install Python **≥3.9**, Node.js **≥22.13.0**, and npm. You do not need WeChat MP administrator access; scan the QR code with a WeChat account that has WeRead.

```bash
git clone https://github.com/konglong87/wechat-download-skill.git
cd wechat-download-skill
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login   # scan and confirm on your phone
python3 scripts/download_weread.py status  # auth.status should be authenticated
python3 scripts/download_weread.py pace-status  # local pacing state; no search request
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

- Each successful article becomes one Markdown file with the original URL, account, and publication time; existing files are skipped. Ordinary articles may retain remote embedded image links. For **image posts**, every listed original image is downloaded into a local `_images/` directory and referenced relatively from Markdown. Missing images or files failing type/size checks are a failure. All 15 files in this live test were also decoded independently.
- Empty normal-article bodies, page chrome, and image posts missing any declared original image are rejected. Batch failures go to `failures.json` with a nonzero exit code. Check both counts and actual file content: successful search or listing does not prove readable articles.
- Search/listing briefly returned `-2041` during live testing, then recovered without a separate phone verification prompt. Stop on rate limits and try later rather than bypassing challenges.
- Upstream may mark even a long result `completeness=unverified`. A plausible full body is not a byte-for-byte comparison to the original. Deleted, restricted, paid, or otherwise unavailable content may fail. Archive only content you may access and use.

## Known link: identify the account without WeRead search

If `search` returns `-2041`, **do not repeat search**. Given a public article URL, `identify` checks the visible publisher name and the page's unique numeric `biz` value without contacting WeRead or solving a challenge:

```bash
python3 scripts/download_weread.py identify 'https://mp.weixin.qq.com/s/TG5KkixnncIrunVZF2ROKQ' --expect-account '孔小黑进城'
# Live result: MP_WXS_3227210349. Only after the pacing cooldown expires:
python3 scripts/download_weread.py list MP_WXS_3227210349 0 3
```

The ID identifies this **known article's publisher**; it does not prove that the recent-article list is accessible or that indexed search results are current. Redirects, verification shells, publisher mismatches and ambiguous IDs fail closed. A list-level `-2041` remains a stop signal; neither this command nor the public-page body fallback bypasses a CAPTCHA.

## Adaptive pacing and verification circuit

All authenticated WeRead CLI search/list/read operations share an inter-process lock and a private `~/.local/state/wechat-download-skill/weread-pacing.json` file (timestamps and counters only, mode `0600`; no credentials). Normal requests are staggered by **5–10 seconds**. Explicit rate limits/HTTP 429 trigger exponential **60-second to 30-minute** cooldowns. A `-2041` human-verification challenge has a separate **30-minute to 24-hour** circuit: later processes fail without contacting WeRead until the cooldown expires, when a single low-frequency probe is allowed. Another challenge doubles the cooldown; success clears it. This is not a way around required official-client verification. Remaining cooldowns longer than 15 seconds fail fast rather than tying up a scheduled job; `status`/`login` remain available, but an authenticated `status` does not prove the challenge is resolved.

```bash
python3 scripts/download_weread.py pace-status
# Only after completing any requested verification in the official client:
python3 scripts/download_weread.py pace-reset --verified
```

Never run `pace-reset` automatically in a scheduler. Treat an active circuit as a failed check and wait for a later run. For a known URL blocked locally by the WeRead circuit, the independent public original-page reader may still work; then exact-item public RSS is attempted. A blocked page or missing feed remains a failure.

## Bounded retries, normal articles, image posts, and exact-item RSS

- A missing/insufficient body, timeout, or transient service error gets **up to three retries after the initial request**, with **10/30/90-second backoff** and a forced CLI cache refresh. Explicit verification, rate limits, `-2041`, and blocked pages are **not** hammered. The previous `HEAD` redirect guard was removed: even an article that succeeds with a fresh WeRead CLI request returned a challenge to independent `HEAD`, so HEAD alone is not proof that a GET body is unavailable.
- After the eInk source fails, the adapter makes one bounded, no-redirect request to the public article URL with the pinned eInk user agent. It accepts a substantive visible `#js_content` or long `content_noencode` for normal articles. For `item_show_type=8` image posts, it archives the complete `picture_page_info_list` gallery plus the caption; teasers alone never count as success. An explicitly configured Web session then gets one try before RSS. Finally the adapter uses the verified account name from its response, or an explicit `--rss-account 'Exact account name'`, to look up the public RSS catalogue. It saves a `.md` file only if the feed has the **same article URL identity** (short link or all `__biz`/`mid`/`idx`/`sn` fields) and a nontrivial `content:encoded` body. The Markdown records its third-party RSS provenance. A similar title or a neighboring article is never substituted.
- Missing catalogue entries, a slow feed, no exact article match, or a short RSS body remain failures with nonzero exit status and `failures.json` for batches. Search/list failures before an article URL is available cannot be matched to an exact RSS item; use the standalone RSS command after confirming the account.

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads --rss-account 'Exact account name'
```

The investigation found two distinct formats. The upstream CLI falsely rejected the normal Ontology article because its body discusses “需要验证”; structured body extraction saved it. Posts 1 and 3 had only 326/447-character text previews because they are **image posts (`item_show_type=8`)**, not regular text articles. The gallery adapter archived their 7 and 8 original CDN images. All 15 files decoded successfully, dimensions matched the page declarations, and representative original images were visually inspected. This **3/3** result archives the actual media, not OCR text from inside those images. Neither an unauthenticated Web session nor the missing public RSS catalogue was needed.


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

## Scheduled checks: verify text and local image galleries

An agent may periodically run `status`, `list ID 0 10`, then `download ID 10 ./wechat_downloads/account` in a **persistent** output directory, reporting newly saved Markdown files, skipped files, failures, and the process exit code. On a nonzero exit, do not report a successful check or “no new articles.” Choose a count large enough to cover new posts since the last run. Scheduling belongs to the user's Codex/Claude/other agent; this project does not install background jobs and saves a separate Web session secret only if the user explicitly invokes `web-cookie`.

**October 28, 2026: all three newest 匿名测试公众号 post packages archived (one text body, two complete image galleries with 15 local files). A repeat batch run reported `Skipped: 3, Failed: 0` and cleared the old `failures.json`.** Scheduled agents must still check exit status and every local image reference; future inaccessible/new-format posts may fail. Text-only agents need optional OCR and human review to search words inside pictures.

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

Architecture: `download_weread.py → weread_client.py → [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni) (MIT) → WeRead index and public article URLs`. The strict `wechat_page_body.py` and `wechat_picture_body.py` extract visible text or the complete public image-post gallery; optional `weread_web_body.py` uses only a user-authorized Web session; exact RSS is the final fallback. The legacy `download_wechat.py`/`start_wechat_api.sh` route is compatible with [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api), but its article-list endpoint returned `ret=200013, freq control` in live testing and is not the recommended batch route. No third-party source is copied; do not bypass verification or access controls.
