# wechat-download-skill

An agent skill and CLI for discovering WeChat official accounts through a **QR-authenticated WeRead account** and saving readable article text as Markdown. Known article URLs can be downloaded directly. Public RSS is a login-free fallback; the legacy WeChat MP admin route is retained only for compatibility.

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

The installer pins `weread-omni@0.1.2` under `~/.local/share/wechat-download-skill/weread-omni/`, without changing global npm packages. The upstream CLI owns the credentials in your home directory; this skill does not read or commit cookies. The phone's WeRead device list may show the new login as **BOOX**. WeRead authentication is separate from the WeChat MP admin session.

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

## Scheduled checks: article discovery, not guaranteed full-text delivery

An agent may periodically run `status`, `list ID 0 10`, then `download ID 10 ./wechat_downloads/account` in a **persistent** output directory, reporting newly saved Markdown files, skipped files, failures, and the process exit code. On a nonzero exit, do not report a successful check or “no new articles.” Choose a count large enough to cover new posts since the last run. Scheduling belongs to the user's Codex/Claude/other agent; this project does not install background jobs or retain login secrets.

**Live test on October 28, 2026: the three newest indexed posts from 匿名测试公众号 were listed, but all three returned `SOURCE_CONTENT_INSUFFICIENT`; `0/3` new bodies were saved. The public RSS catalogue did not include that account.** This path can currently detect new article metadata, but **unattended delivery of the latest full text for that account is not established**. A different known URL from the same account was successfully downloaded; availability varies by article.

## Login-free RSS fallback

For a catalogued account with a reachable third-party feed:

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

Architecture: `download_weread.py → weread_client.py → [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni) (MIT) → WeRead index and public article URLs`. RSS is an independent fallback. The legacy `download_wechat.py`/`start_wechat_api.sh` route is compatible with [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api), but its article-list endpoint returned `ret=200013, freq control` in live testing and is not the recommended batch route. No third-party source is copied; do not bypass verification or access controls.
