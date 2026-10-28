# Changelog

## v1.3.0 — 2026-10-28

- Make QR-authenticated WeRead the documented primary route; keep public RSS as a limited fallback and the old MP admin endpoint as compatibility only.
- Live-validate a known 匿名测试公众号 article URL: 40,490-byte Markdown file, about 19,832 body characters, with beginning/middle/end visually inspected. This does **not** prove every article is readable or byte-identical to the original.
- Live-test the same account's three newest indexed articles: listing succeeded, all three returned `SOURCE_CONTENT_INSUFFICIENT`, and **0/3 full bodies were saved**. The public RSS catalogue did not contain the account. Scheduled metadata checks are possible, but reliable unattended full-text delivery is **not** verified.
- Fail closed on short WeRead previews. Improve batch error titles and remove stale `failures.json` after a successful retry. Tests: 22 passing.
- Update Chinese/English onboarding, Agent Skill guidance, GitHub About description and discovery topics.
