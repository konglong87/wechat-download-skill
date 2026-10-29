## Unreleased — 2026-10-29

- Change the recommended route to **explicit public article URL → independent direct-page downloader → shared atomic Markdown/image archive**. Add `scripts/download_public.py url|batch`, strict account-name validation, manifest deduplication, paced batch downloads, and challenge/access-refusal stop conditions; no WeRead search, login, or Cookie is used.
- Rewrite README, English README, and SKILL as **Agent-first** documentation: natural-language requests are the user interface; shell commands are internal Agent implementation details. Document the discovery ladder, human-interaction boundaries, and the fact that account-name-only newest-post discovery is not guaranteed.
- Extract shared archive and public-page identity components from the legacy WeRead CLI, preserving its test behavior. Add route-specific tests.
- Live-check an explicitly supplied 匿名测试公众号 article: `EXAMPLE_ARTICLE` saved as a 44,395-byte Markdown file on 2026-10-29. This does **not** prove fully automated discovery of an account's newest three posts; title-only/VIP indexes and stale third-party caches are not substituted for original links.

# Changelog

## Unreleased

- Verify an owner-authorized official MP dashboard discovery route on 2026-10-29: after the user completed WeChat quick login, approved the displayed profile permission, and selected 孔小黑进城, the dashboard showed the three latest published URLs. Downloading each URL archived **3/3** posts (two image galleries with 1 + 2 local originals, one ordinary article). This route is limited to accounts the user manages and does not resolve WeRead eInk `-2041` or provide an unattended admin API.
- Parse the public article's Open Graph title and validated creation time when the WeRead index lacks metadata, and match existing archives by exact source URL so changing upstream `reviewId` does not duplicate a direct download. Document that this user's WeRead App has no “Settings → Privacy → reauthorize public accounts” option.

- Document evidence-qualified `-2041` recovery: the pinned CLI already sends `synckey=0` on initial `/mp/chapters`, unlike a separate Android-client bug; upstream classifies the current session fingerprint as challenged. Official Web CAPTCHA and last-resort device cleanup are user-operated possibilities with conflicting community outcomes, not an automated fix. Do not share secrets or reset the local circuit without an actual verification event.

- Add public-article `identify URL --expect-account NAME`: validate the visible publisher/title and a unique numeric base64 `biz`, derive the candidate `MP_WXS_<digits>` without a WeRead search request. Verified on the supplied 孔小黑进城 article as `MP_WXS_3227210349`. A known ID avoids the challenged `/store/search` path, but a single `/mp/chapters` probe after cooldown also returned `-2041`. At that stage the unauthenticated public profile returned a verification page and RSS lacked this account, so newest-three discovery was blocked **through those routes**; the later owner-dashboard route above supplied the three URLs. Never bypass a verification challenge.

- Add a cross-process, persisted WeRead request pacer: randomized 5–10-second spacing, exponential 60-second–30-minute rate-limit cooldown and separate `-2041` verification circuit with single probe after 30-minute–24-hour backoff. Expose `pace-status` and explicit `pace-reset --verified`; lengthen transient article-body retries to 10/30/90 seconds. A known article URL can still try the independent public original-page reader while the WeRead gate is locally closed, followed by exact-item RSS; an actual upstream -2041 does not trigger an immediate extra page request. Never store authentication in pacing state or hammer a challenge. On 2026-10-29, a known 匿名测试公众号 article URL was fetched through this public-page fallback while the WeRead challenge circuit remained closed (44,307-byte Markdown); this does not establish the newest posts for 孔小黑进城.

- Add strict `item_show_type=8` image-post support: parse the actual `picture_page_info_list`, download every HTTPS original image from the allowlisted CDN, verify image magic and bounds, save atomic Markdown plus local `_images/` assets, and treat missing files as incomplete. Latest-three 匿名测试公众号 now archive **3/3**: one normal text article and two image galleries (7 + 8 images; 15/15 decoded and dimension-checked). No OCR claim. A repeat batch returned `Skipped: 3, Failed: 0` and cleared `failures.json`.

- Re-test three newest 匿名测试公众号 posts individually. Fix an upstream false positive: the Ontology article contains the phrase “需要验证” in its genuine body, but weread-omni scans the entire HTML and rejects it. A strict normal-page body adapter now saves this article (42,669-byte Markdown, 17,671 body characters); the other two expose only 326/447-character previews and remain failures. At that intermediate stage the outcome was **1/3**; subsequent image-gallery support archived the remaining two media posts.
- Remove the previous HEAD-based challenge guard: a known article that succeeds with `--refresh` also redirects on independent HEAD. Do not equate HEAD status with the WeRead GET body. Reject actual verification redirects during the bounded page request instead.

- Add an opt-in, separate WeRead Web body adapter using a user-supplied owner-only Cookie file (`web-cookie` hidden prompt); never log or commit credentials, reject redirects, login/challenge shells, and short bodies. Keep exact RSS as the final fallback. Authenticated Web body success is not yet verified.
- A separate WeRead Web session remains optional and unproven for the two still-missing articles: without it, the endpoint answered `errCode=-2010`. Independently issued HEAD/browser-style requests may challenge even when the pinned eInk GET returns a normal article; only the actual body response determines success.

- Retry transient WeRead article-body failures up to three additional times (2/4/8-second backoff, forced refresh); stop immediately on explicit rate limits or verification challenges.
- On failure, automatically consult the public RSS catalogue for the verified account and save only an exact matching article with nontrivial `content:encoded`; mark third-party provenance. Accept `--rss-account` when the name is unavailable upstream. Do not substitute other feed items.
- Before the public-body parser fix, the three newest 匿名测试公众号 posts saved 0/3. The exact RSS catalogue did not include this account; the provider also timed out intermittently.

## v1.3.0 — 2026-10-28

- Make QR-authenticated WeRead the documented primary route; keep public RSS as a limited fallback and the old MP admin endpoint as compatibility only.
- Live-validate a known 匿名测试公众号 article URL: 40,490-byte Markdown file, about 19,832 body characters, with beginning/middle/end visually inspected. This does **not** prove every article is readable or byte-identical to the original.
- Live-test the same account's three newest indexed articles: listing succeeded, all three returned `SOURCE_CONTENT_INSUFFICIENT`, and **0/3 full bodies were saved**. The public RSS catalogue did not contain the account. Scheduled metadata checks are possible, but reliable unattended full-text delivery is **not** verified.
- Fail closed on short WeRead previews. Improve batch error titles and remove stale `failures.json` after a successful retry. Tests: 22 passing.
- Update Chinese/English onboarding, Agent Skill guidance, GitHub About description and discovery topics.
