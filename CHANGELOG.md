## Unreleased — 2026-10-29

- Change the recommended route to **explicit public article URL → independent direct-page downloader → shared atomic Markdown/image archive**. Add `scripts/download_public.py url|batch`, strict account-name validation, manifest deduplication, paced batch downloads, and challenge/access-refusal stop conditions; no WeRead search, login, or Cookie is used.
- Rewrite README, English README, and SKILL as **Agent-first** documentation: natural-language requests are the user interface; shell commands are internal Agent implementation details. Document the discovery ladder, human-interaction boundaries, and the fact that account-name-only newest-post discovery is not guaranteed.
- Extract shared archive and public-page identity components from the legacy WeRead CLI, preserving its test behavior. Add route-specific tests.
- Live-check an explicitly supplied public article URL with the independent public-page CLI on 2026-10-29. This does **not** prove fully automated discovery of an account's newest three posts; title-only/VIP indexes and stale third-party caches are not substituted for original links.

# Changelog

## Unreleased

- Verify an owner-authorized official MP dashboard discovery route on 2026-10-29: after the user completed WeChat quick login, approved the displayed profile permission, and selected 孔小黑进城, the dashboard showed the three latest published URLs. Downloading each URL archived **3/3** posts (two image galleries with 1 + 2 local originals, one ordinary article). This route is limited to accounts the user manages and does not resolve WeRead eInk `-2041` or provide an unattended admin API.
- Parse the public article's Open Graph title and validated creation time when the WeRead index lacks metadata, and match existing archives by exact source URL so changing upstream `reviewId` does not duplicate a direct download. Document that this user's WeRead App has no “Settings → Privacy → reauthorize public accounts” option.

- Document evidence-qualified `-2041` recovery: the pinned CLI already sends `synckey=0` on initial `/mp/chapters`, unlike a separate Android-client bug; upstream classifies the current session fingerprint as challenged. Official Web CAPTCHA and last-resort device cleanup are user-operated possibilities with conflicting community outcomes, not an automated fix. Do not share secrets or reset the local circuit without an actual verification event.

- Add public-article `identify URL --expect-account NAME`: validate the visible publisher/title and a unique numeric base64 `biz`, derive the candidate `MP_WXS_<digits>` without a WeRead search request. Verified on the supplied 孔小黑进城 article as `MP_WXS_3227210349`. A known ID avoids the challenged `/store/search` path, but a single `/mp/chapters` probe after cooldown also returned `-2041`. At that stage the unauthenticated public profile returned a verification page and RSS lacked this account, so newest-three discovery was blocked **through those routes**; the later owner-dashboard route above supplied the three URLs. Never bypass a verification challenge.

- On 2026-10-29, a known public article URL was fetched through the independent public-page fallback while the WeRead challenge circuit remained closed; that did not establish latest-post discovery for another account.

- Add strict `item_show_type=8` image-post support: parse the actual `picture_page_info_list`, download every HTTPS original image from the allowlisted CDN, verify image magic and bounds, save atomic Markdown plus local `_images/` assets, and treat missing files as incomplete. In a three-post test, one normal text article and two complete image galleries were archived. No OCR claim. A repeat batch skipped the complete archives and cleared stale failures.

- Re-test three posts individually. Fix an upstream false positive: a genuine article body contained “需要验证”, but the pinned CLI scanned the entire HTML and rejected it. A strict normal-page body adapter recovered that text article; the other two exposed only short previews because their content was carried in image galleries. Subsequent image-gallery support archived those media posts.
- Remove the previous HEAD-based challenge guard: a known article that succeeds with `--refresh` also redirects on independent HEAD. Do not equate HEAD status with the WeRead GET body. Reject actual verification redirects during the bounded page request instead.

- Add an opt-in, separate WeRead Web body adapter using a user-supplied owner-only Cookie file (`web-cookie` hidden prompt); never log or commit credentials, reject redirects, login/challenge shells, and short bodies. Keep exact RSS as the final fallback. Authenticated Web body success is not yet verified.
- A separate WeRead Web session remains optional and unproven for the two still-missing articles: without it, the endpoint answered `errCode=-2010`. Independently issued HEAD/browser-style requests may challenge even when the pinned eInk GET returns a normal article; only the actual body response determines success.

- Retry transient WeRead article-body failures up to three additional times (2/4/8-second backoff, forced refresh); stop immediately on explicit rate limits or verification challenges.
- On failure, automatically consult the public RSS catalogue for the verified account and save only an exact matching article with nontrivial `content:encoded`; mark third-party provenance. Accept `--rss-account` when the name is unavailable upstream. Do not substitute other feed items.
- Before the public-body parser fix, a targeted three-post test saved no complete bodies. The exact RSS catalogue did not include that test account; the provider also timed out intermittently.

## v1.3.0 — 2026-10-28

- Make QR-authenticated WeRead the documented primary route; keep public RSS as a limited fallback and the old MP admin endpoint as compatibility only.
- Live-validate a known public article URL: substantive Markdown with beginning/middle/end visually inspected. This does **not** prove every article is readable or byte-identical to the original.
- Live-test the same account's three newest indexed articles: listing succeeded, all three returned `SOURCE_CONTENT_INSUFFICIENT`, and **0/3 full bodies were saved**. The public RSS catalogue did not contain the account. Scheduled metadata checks are possible, but reliable unattended full-text delivery is **not** verified.
- Fail closed on short WeRead previews. Improve batch error titles and remove stale `failures.json` after a successful retry. Tests: 22 passing.
- Update Chinese/English onboarding, Agent Skill guidance, GitHub About description and discovery topics.
