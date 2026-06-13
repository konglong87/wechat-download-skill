# wechat-download — Claude Code skill for downloading WeChat official account articles

A [Claude Code](https://claude.ai/code) skill that wraps
[wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) to
download articles from any WeChat official account (公众号).

## What it does

```
┌─────────────────┐     HTTP      ┌───────────────────────┐     TLS      ┌──────────┐
│  Claude Code    │ ────────────→  │  wechat-download-api  │ ──────────→  │  微信后台 │
│  + this skill   │               │  (localhost:8765)      │  Chrome TLS │          │
└─────────────────┘               └───────────────────────┘             └──────────┘
```

- **Search** — find an official account by name, get its `fakeid`
- **List** — paginate through all published articles
- **Download** — fetch full text content for every article, save as `.txt`
- **RSS** — generate an RSS 2.0 feed URL for any account

Features built into the download script:
- Resume (skip already-downloaded files)
- Rate-limit backoff (auto-waits when Rate limited)
- Failure log (`failures.json`)

## Quick start

### 1. Deploy wechat-download-api

```bash
git clone https://github.com/tmwgsicp/wechat-download-api.git
cd wechat-download-api
cp env.example .env
pip3 install -r requirements.txt
```

Prerequisites: Python 3.8+, pip, a C compiler (for `curl_cffi`).

### 2. Start the API

```bash
bash scripts/start_wechat_api.sh
# → http://localhost:8765
```

> **Port note**: this skill defaults to `8765` instead of upstream's `5000` (macOS often reserves 5000). If you started the API with upstream's `start.sh` on port `5000`, prefix commands with `WECHAT_API_URL=http://localhost:5000`.

### 3. Install this skill in Claude Code

```bash
ln -s "$(pwd)" ~/.claude/skills/wechat-download
```

### 4. Scan QR code to log in

Open `http://localhost:8765/login.html` in a browser and scan with
WeChat (you need a WeChat Official Account — any subscription or
service account works).  Credentials last ~4 days.

### 5. Download articles

In Claude Code, just say:

> Download articles from <account name>

Or use the CLI directly:

```bash
python3 scripts/download_wechat.py search "account name"
# → fakeid: <base64-encoded-id>

python3 scripts/download_wechat.py download "<fakeid>" 200 ./output
# → articles downloaded to ./output
```

## Commands

```bash
python3 scripts/download_wechat.py status                    # health check
python3 scripts/download_wechat.py search "name"             # find account
python3 scripts/download_wechat.py list <fakeid> [begin] [n] # list articles
python3 scripts/download_wechat.py download <fakeid> [n] [dir]  # download all
python3 scripts/download_wechat.py rss <fakeid>              # RSS URL
```

## Files

```
wechat-download/
├── SKILL.md                    # Skill handbook (Claude Code reads this)
├── .gitignore
├── README.md                   # This file
└── scripts/
    ├── download_wechat.py      # Main CLI tool
    ├── start_wechat_api.sh     # Start the background API service
    ├── stop_wechat_api.sh      # Stop it
    └── requirements.txt        # Python deps for the CLI
```

## Common issues

| Symptom | Fix |
|---------|-----|
| `address already in use` | `bash scripts/start_wechat_api.sh 9876` |
| All downloads fail with "no URL" | Field is `link`, not `url` |
| Rate limited | Script auto-retries; increase `MIN_DELAY` if persistent |
| WeChat security verification | Open the article URL in browser, verify, wait 30 min |
| Login expired | Re-scan QR at `/login.html` |
| curl_cffi won't install | `xcode-select --install` (macOS) or `apt install build-essential libcurl4-openssl-dev` (Linux) |

## What if I don't have a WeChat Official Account?

Alternative approaches (lower coverage):
1. Search `"account name" mp.weixin.qq.com/s` on search engines → scrape `#js_content`
2. Look for reprints on guancha.cn, 36kr, finance.sina.com.cn
3. Use mirror sites like jintiankansha.me (usually requires VIP for full text)

## License

MIT

## Credits

- [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) (AGPL 3.0) — the API service this skill wraps