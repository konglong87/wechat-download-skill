# wechat-download

A Claude Code skill for downloading WeChat Official Account articles.

Chinese version: [README.md](README.md)

## Simplest Usage

After installing this skill, just tell Claude Code or your agent:

```text
Download articles from the XXX WeChat official account
```

Or:

```text
Download the latest 200 articles from the XXX WeChat official account
```

That's it. You do not need to manually install the underlying API service or any Python dependencies for this skill. The agent follows the skill instructions, starts the local service, downloads `wechat-download-api` if it is missing, and installs the service dependencies automatically.

The only manual step is scanning the login QR code with a WeChat Official Account administrator account when prompted.

## Installation

```bash
git clone git@github.com:konglong87/wechat-download-skill.git ~/.claude/skills/wechat-download
```

If you already cloned this repository somewhere else, link it into Claude's skill directory:

```bash
ln -s /path/to/wechat-download-skill ~/.claude/skills/wechat-download
```

## What The Agent Does Automatically

When you ask the agent to download articles, it will:

1. Check whether the local `wechat-download-api` service is available.
2. Run `scripts/start_wechat_api.sh` if the service is not running.
3. Clone `wechat-download-api` into the skill directory if it is missing.
4. Install the Python packages required by the underlying service.
5. Ask you to open `http://localhost:8765/login.html` and scan the QR code.
6. Search for the official account and get its `fakeid`.
7. Batch download article content into a local output directory.

The default port is `8765`. If you already started upstream `wechat-download-api` on its default port `5000`, the agent can use it with `WECHAT_API_URL=http://localhost:5000`.

## Manual Commands

You usually do not need these. They are mainly for the agent or troubleshooting.

```bash
cd ~/.claude/skills/wechat-download

bash scripts/start_wechat_api.sh               # Start service on port 8765
python3 scripts/download_wechat.py status      # Check service health
python3 scripts/download_wechat.py search "account name"
python3 scripts/download_wechat.py download "fakeid" 200 ./output
python3 scripts/download_wechat.py list "fakeid" 0 50
python3 scripts/download_wechat.py rss "fakeid"
```

## Login

Downloading historical account articles requires access to WeChat Official Platform article-list APIs, so you need to log in with a WeChat Official Account administrator account.

1. Open `http://localhost:8765/login.html`
2. Scan the QR code with the administrator's WeChat
3. Credentials are saved locally to `.env`
4. Credentials usually expire after about 4 days; scan again when needed

If you do not have a WeChat Official Account administrator account, the agent can only try fallback approaches such as search engines, repost platforms, or mirror sites. Coverage will be much lower.

## Files

```text
wechat-download/
├── SKILL.md
├── README.md
├── README.en.md
└── scripts/
    ├── download_wechat.py
    ├── start_wechat_api.sh
    └── stop_wechat_api.sh
```

## Common Issues

| Issue | Fix |
| --- | --- |
| Port is already in use | Ask the agent to use another port, or run `bash scripts/start_wechat_api.sh 9876` |
| Login expired | Open `http://localhost:8765/login.html` and scan again |
| WeChat security verification | Slow down, open the prompted URL in a browser, complete verification, and retry later |
| Some articles fail | The article may be deleted, restricted, an ad, or image-only; skipping is usually fine |
| `curl_cffi` install fails | On macOS, install Xcode CLT with `xcode-select --install` |

## Underlying Project

This skill wraps [tmwgsicp/wechat-download-api](https://github.com/tmwgsicp/wechat-download-api).
