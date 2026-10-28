# wechat-download

An agent skill for downloading WeChat official-account articles. **A public RSS path has been live-tested for catalogued accounts**; an experimental WeRead path targets broader discovery (live QR login validated; full-body retrieval still blocked) to discover article links and retrieve readable content. The legacy WeChat MP article-list endpoint returned `ret=200013, freq control` in the October 2026 live test; an API health check does not establish that batch downloads work.

## Login-free public RSS (live-tested)

```bash
python3 scripts/download_rss.py search "小众软件"
python3 scripts/download_rss.py list 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml'
python3 scripts/download_rss.py download 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml' 1 ./wechat_downloads
```

This adapter accepts only fixed-form HTTPS Wechat2RSS feed URLs; name search covers the public catalogue. It saves each feed item’s `content:encoded` body to `.txt`. It does not bypass WeChat verification or require login. A live October 28, 2026 test found 20 recent entries for 小众软件 and saved/read back one 3,223-byte article. The third-party feed does **not** guarantee arbitrary accounts, complete history, or independently verified full text. Images remain remote links.

## Quick start

The public RSS route requires only Python **>=3.9**. The broader experimental WeRead route requires Node.js **>=22.13.0**, Python **>=3.9**, and a WeRead-enabled WeChat account. WeRead login is separate from WeChat MP administrator login.

```bash
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login  # scan the WeRead QR code
python3 scripts/download_weread.py status
python3 scripts/download_weread.py search "account name"
python3 scripts/download_weread.py list MP_WXS_1234567890 0 10
python3 scripts/download_weread.py download MP_WXS_1234567890 20 ./wechat_downloads
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads
```

Use the WeRead `MP_WXS_<digits>` account ID returned by search, not a legacy MP `fakeid`. To use an existing CLI, set `WEREAD_CLI`; to select a different logged-in account, set `WEREAD_ACCOUNT`. Use `--refresh` before a command to bypass the CLI cache.

The adapter invokes the pinned MIT-licensed `weread-omni@0.1.2` and never reads or prints its cookies. The install script stores it in `~/.local/share/wechat-download-skill/weread-omni/`, not the global npm location. Results are one Markdown file per article, with source URL and metadata. Images remain remote URLs, not local image files. Completed files are skipped; failures are written to `failures.json` and return a nonzero exit status. Paging supports up to 1,000 articles per run (default 200), subject to upstream availability and rate limits.

Live test on 2026-10-28: QR login and authentication succeeded; the phone app showed the newly logged-in BOOX device without a separate verification prompt. Search and listing initially returned `-2041` but both succeeded on a later retry, so an official-client challenge is not established. Some full-text retrieval remains blocked: two known URLs returned `readable` with only 21 characters of navigation chrome (`completeness=unverified`), even after refresh, and an older article returned `SOURCE_CONTENT_INSUFFICIENT`. A user-provided article from 匿名测试公众号 did download as a 40,490-byte Markdown file (about 19,832 body characters); its beginning, middle, and end were inspected and screenshot-verified. Because upstream still labels completeness unverified, this is not a byte-for-byte comparison with the original and does not imply arbitrary articles work. The adapter rejects empty previews instead of claiming a download. Public RSS previously saved full bodies for indexed recent items, but a later feed request timed out or remained incomplete; availability depends on the third-party source.

WeRead's unpublished article index can be incomplete; deleted, restricted, and paid content may not be readable. The skill does **not** silently subscribe to an account or bypass verification. Subscribe in the WeRead app, or explicitly approve a subscription first. Archive only content you may lawfully access and use.

The legacy `scripts/start_wechat_api.sh` and `scripts/download_wechat.py` remain for compatibility and known-link troubleshooting, but are no longer the recommended batch route. The old downloader now reports failed/empty lists as errors instead of claiming success.

Uses [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni) (MIT) as an external CLI and retains compatibility with [tmwgsicp/wechat-download-api](https://github.com/tmwgsicp/wechat-download-api). No third-party source code is copied into this repository.
