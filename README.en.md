# wechat-download

An agent skill for downloading WeChat official-account articles. **An experimental WeRead path is available (live QR-login validation pending)** to discover article links and retrieve readable content. The legacy WeChat MP article-list endpoint returned `ret=200013, freq control` in the October 2026 live test; an API health check does not establish that batch downloads work.

## Quick start

Requires Node.js **>=22.13.0**, Python **>=3.9**, and a WeRead-enabled WeChat account. WeRead login is separate from WeChat MP administrator login.

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

WeRead's unpublished article index can be incomplete; deleted, restricted, and paid content may not be readable. The skill does **not** silently subscribe to an account or bypass verification. Subscribe in the WeRead app, or explicitly approve a subscription first. Archive only content you may lawfully access and use.

The legacy `scripts/start_wechat_api.sh` and `scripts/download_wechat.py` remain for compatibility and known-link troubleshooting, but are no longer the recommended batch route. The old downloader now reports failed/empty lists as errors instead of claiming success.

Uses [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni) (MIT) as an external CLI and retains compatibility with [tmwgsicp/wechat-download-api](https://github.com/tmwgsicp/wechat-download-api). No third-party source code is copied into this repository.
