# wechat-download-skill

**Recommended route: archive known public WeChat article URLs directly, without WeRead authentication or eInk search.** Save verified visible article bodies as Markdown, and image posts with their local original images. A URL list supports one-by-one batch archiving; challenge pages, mismatched accounts, and teaser-only pages fail closed. Older WeRead, owner-dashboard, and public RSS paths remain optional, **not the default**.

> **Live check, 2026-10-29:** An explicitly supplied article URL from the owner-managed `孔小黑进城` account produced a **7,539-byte** Markdown file using the standalone public-page CLI. The owner dashboard also supplied three published links that were archived. A successful known URL does **not** prove that the latest posts of any account can be discovered unattended. Public RSS covers only indexed accounts; title-only/VIP directories are not original-URL sources.

## How other Agents use this Skill (natural language first)

This repository is an Agent Skill for Codex, Claude, and similar agents. End users are not expected to open a terminal or run Python commands. A user can simply say:

> Download the latest three posts from “孔小黑进城” and save them to the article archive.

The Agent should identify the account and count, try lawful discovery sources, obtain real `https://mp.weixin.qq.com/s/...` URLs, archive each article, verify the body or image gallery, skip complete duplicates, and report successes, skips, failures, and reasons. The command line is an internal implementation detail, not a user-facing requirement.

The user only needs to help when a platform requires human interaction, such as scanning a QR code, approving an authorization dialog, or normally sharing an article link from the mobile WeChat app.

### Preferred route: archive known public article URLs

When the Agent has one or more legitimately obtained original article URLs, it can save normal posts as Markdown and image posts with local image files. The internal entry point is `scripts/download_public.py`; users do not need to invoke it directly.

It supports normal articles, image posts, exact account-name checks, duplicate skipping, paced batches, and fail-closed handling for challenge pages, redirects, account mismatches, HTTP 403/429, or teaser-only content.

### Agent discovery when only an account name is provided

The Agent may try these lawful sources:

```text
account name
  ├─ indexed public RSS
  ├─ a known article URL supplied by the user
  ├─ the user's authorized official-account dashboard
  ├─ WeRead indexing (optional; may be blocked by -2041)
  └─ a normal share link from the user's mobile WeChat app
```

This is not a guarantee that an account name alone will always yield the latest posts. Title-only indexes, ReadGZH's cache, and public RSS feeds are incomplete sources. If no real article URL can be verified, the Agent should report that discovery is incomplete and ask for a normal shared link—not ask the user to run terminal commands or invent a URL.

### Live-verified boundaries

- `孔小黑进城`: a known original URL was archived as a 7,539-byte normal article; three published links from its owner dashboard yielded one normal article and two image posts with three local originals. Discovery of arbitrary third-party accounts' latest posts is not yet stable.
- Android automatic link extraction and phone-to-computer synchronization have not been validated on the current device; do not promise unattended operation.
- Image text is not OCRed automatically; add OCR separately and review it.

Respect copyright, access permissions, and platform verification. Never bypass challenges, rate limits, or paywalls.

## Legacy route: WeRead (optional, not recommended)

### Install and sign in

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
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/TG5KkixnncIrunVZF2ROKQ' ./wechat_downloads
# Bypass the CLI cache and refetch:
python3 scripts/download_weread.py --refresh url 'https://mp.weixin.qq.com/s/TG5KkixnncIrunVZF2ROKQ' ./wechat_downloads
```

Replace the example with your own `https://mp.weixin.qq.com/s/...` article URL. On success, check the printed `.md` path and size, then inspect the body. The example was verified on a specific date; future availability is not guaranteed.

### Your own MP account: find recent published URLs in the dashboard

This requires **management access to that account**; it does not discover posts from arbitrary third-party accounts. In the in-app browser, open `https://mp.weixin.qq.com/`, select “WeChat quick login,” review and confirm the permission prompt yourself, and select the managed account. Read the titles, dates, and original URLs under “Recent publications” or Content → Publication records. Download each URL using `python3 scripts/download_weread.py url 'ARTICLE_URL' ./wechat_downloads/ACCOUNT --rss-account 'ACCOUNT'`. Do not provide browser cookies, dashboard tokens, or access to drafts/publishing. This MP login is **not** WeRead eInk verification and does not resolve `-2041`.

On October 29, 2026, the managed 孔小黑进城 dashboard listed [Oct 15](https://mp.weixin.qq.com/s/QSBBXzcE8otJdVYIeqUCIg), [Sep 7](https://mp.weixin.qq.com/s/k-CZ7JH-HLiVI7s2pJzL7w), and [Sep 6](https://mp.weixin.qq.com/s/TG5KkixnncIrunVZF2ROKQ). All **3/3** were saved individually: the first two are image posts with **1 + 2 original images and captions**, and the third is a normal text article. The public-page reader now fills image-post title/publication metadata; URL-based deduplication avoids duplicates when an upstream `reviewId` changes. This is **interactive owner-side discovery, not an unattended MP dashboard API**.

### Start with an account name

```bash
python3 scripts/download_weread.py search '孔小黑进城'
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

The ID identifies this **known article's publisher**; it does not prove that the WeRead recent-article list is accessible or current. Redirects, verification shells, publisher mismatches and ambiguous IDs fail closed. A list-level `-2041` remains a stop signal. **Observed October 29, 2026:** the known 孔小黑进城 article archived from its public page (7,523-byte Markdown), but one `/mp/chapters` attempt after cooldown still returned `-2041`. The unauthenticated public profile showed a verification page and the public RSS catalogue lacked the account. **Those routes** did not reveal the newest three; the later authenticated **owner's MP dashboard** did, and each resulting URL was archived as described above. This does not restore WeRead eInk discovery or enable unattended discovery for arbitrary third-party accounts.

## Adaptive pacing and verification circuit

All authenticated WeRead CLI search/list/read operations share an inter-process lock and a private `~/.local/state/wechat-download-skill/weread-pacing.json` file (timestamps and counters only, mode `0600`; no credentials). Normal requests are staggered by **5–10 seconds**. Explicit rate limits/HTTP 429 trigger exponential **60-second to 30-minute** cooldowns. A `-2041` human-verification challenge has a separate **30-minute to 24-hour** circuit: later processes fail without contacting WeRead until the cooldown expires, when a single low-frequency probe is allowed. Another challenge doubles the cooldown; success clears it. This is not a way around required official-client verification. Remaining cooldowns longer than 15 seconds fail fast rather than tying up a scheduled job; `status`/`login` remain available, but an authenticated `status` does not prove the challenge is resolved.

```bash
python3 scripts/download_weread.py pace-status
# Only after completing any requested verification in the official client:
python3 scripts/download_weread.py pace-reset --verified
```

Never run `pace-reset` automatically in a scheduler. Treat an active circuit as a failed check and wait for a later run. For a known URL blocked locally by the WeRead circuit, the independent public original-page reader may still work; then exact-item public RSS is attempted. A blocked page or missing feed remains a failure.

### Diagnosing `-2041` without assuming a single cause

[Upstream weread-omni](https://github.com/teng-lin/weread-omni/blob/main/src/api/mobile.ts#L104-L112) treats `-2041` as a session-fingerprint human-verification challenge. A [different Android client's bug](https://github.com/x554960766/wechat-mp-tools/issues/22) produced the same code when `synckey` was missing. This pinned CLI already sends `synckey=0` on the first `/mp/chapters` request; `/store/search` also failed, so do not blindly copy that other client's parameter fix or promise that waiting suffices.

A user may personally open a public-account article in the **official WeRead website** and complete any CAPTCHA displayed. [Community reports](https://github.com/finlater/weread.koplugin/issues/62) conflict about whether this restores a separate eInk session. In this test, the phone app's Settings → Privacy had **no** “reauthorize public accounts” option; do not keep directing users there. Clearing logged-in devices and scanning in again is a **last resort** that logs devices out and is not guaranteed to work. Never share cookies or verification codes with an agent. Only after actual official WeRead verification should the user consider `pace-reset --verified` and one diagnostic probe. Otherwise use known public article URLs individually; for an account the user manages, its own MP dashboard can supply the newest URLs while WeRead discovery remains blocked.

## Legacy route: bounded retries and exact-item RSS

- A missing/insufficient body, timeout, or transient service error gets **up to three retries after the initial request**, with **10/30/90-second backoff** and a forced CLI cache refresh. Explicit verification, rate limits, `-2041`, and blocked pages are **not** hammered. The previous `HEAD` redirect guard was removed: even an article that succeeds with a fresh WeRead CLI request returned a challenge to independent `HEAD`, so HEAD alone is not proof that a GET body is unavailable.
- After the eInk source fails, the adapter makes one bounded, no-redirect request to the public article URL with the pinned eInk user agent. It accepts a substantive visible `#js_content` or long `content_noencode` for normal articles. For `item_show_type=8` image posts, it archives the complete `picture_page_info_list` gallery plus the caption; teasers alone never count as success. An explicitly configured Web session then gets one try before RSS. Finally the adapter uses the verified account name from its response, or an explicit `--rss-account 'Exact account name'`, to look up the public RSS catalogue. It saves a `.md` file only if the feed has the **same article URL identity** (short link or all `__biz`/`mid`/`idx`/`sn` fields) and a nontrivial `content:encoded` body. The Markdown records its third-party RSS provenance. A similar title or a neighboring article is never substituted.
- Missing catalogue entries, a slow feed, no exact article match, or a short RSS body remain failures with nonzero exit status and `failures.json` for batches. Search/list failures before an article URL is available cannot be matched to an exact RSS item; use the standalone RSS command after confirming the account.

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads --rss-account 'Exact account name'
```

On October 29, 2026, the owner-managed `孔小黑进城` dashboard supplied three published article URLs. One was archived as a normal text article; two were **image posts (`item_show_type=8`)** with 1 and 2 local originals respectively. The **3/3** owner-side result archives actual media, not OCR text from the images, and does not establish unattended discovery for third-party accounts.


## Optional authenticated WeRead Web body (experimental)

The [we-mp-rss community implementation](https://github.com/rachelos/we-mp-rss/blob/main/core/wx/model/weread_mp.py) describes `https://weread.qq.com/web/mp/content?reviewId=...`. A WeRead **Web** login is separate from the already-authenticated `weread-omni` eInk account. The endpoint returned `errCode=-2010` (no user) without Web authorization. **No newest-three full-body success has been verified through an authorized Web session.** This undocumented interface may change.

1. Personally sign in at `https://weread.qq.com` in your browser and verify the target article is readable there. Never share a Cookie or verification code in a chat or Issue.
2. If you choose this route, select a same-origin `weread.qq.com` request in your browser's **Network** developer tools. Copy its **Request Headers → Cookie value** (not another site's Cookie). In your own interactive terminal, run `python3 scripts/download_weread.py web-cookie` and paste into the hidden prompt. The private `~/.local/share/wechat-download-skill/weread-web.cookie` file is mode `0600`; `*.cookie` is ignored by Git. Treat this file as a login secret.
3. Re-run the download below. The Cookie is sent only to the fixed WeRead Web content endpoint with no redirects; login/challenge shells and short bodies are rejected. If it fails, the exact-item RSS fallback still runs and the process exits nonzero if no body was saved.

```bash
python3 scripts/download_weread.py --refresh download MP_WXS_3227210349 3 ./wechat_downloads/孔小黑进城 --rss-account '孔小黑进城'
# Optional private-file override: --web-cookie-file /private/path/weread-web.cookie before "download"
```

Re-sign in and re-run `web-cookie` if the session expires; to disable the route, move the private file elsewhere yourself. Never bypass verification, rate limits, or paid access. Verify the three actual `.md` files before scheduling unattended downloads.

## Scheduled checks: validate link discovery first

An agent may periodically run `status`, `list ID 0 10`, then `download ID 10 ./wechat_downloads/account` in a **persistent** output directory, reporting newly saved Markdown files, skipped files, failures, and the process exit code. On a nonzero exit, do not report a successful check or “no new articles.” Choose a count large enough to cover new posts since the last run. Scheduling belongs to the user's Codex/Claude/other agent; this project does not install background jobs and saves a separate Web session secret only if the user explicitly invokes `web-cookie`.

**October 29, 2026: three published `孔小黑进城` posts from the owner dashboard were archived individually (one text article, two image posts with three local originals). This required owner-dashboard links and does not establish unattended discovery for other accounts.** Scheduled agents must still check exit status and every local image reference; future inaccessible/new-format posts may fail. Text-only agents need optional OCR and human review to search words inside pictures.

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
