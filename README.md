# wechat-download

这是一个 Claude Code skill，用来下载微信公众号文章。

English version: [README.en.md](README.en.md)

## 最简单的用法

安装好这个 skill 之后，直接在 Claude Code / agent 里说：

```text
下载 XXX 的公众号文章
```

或者：

```text
帮我下载 XXX 公众号最近 200 篇文章
```

就这样。你不需要手动安装底层 API 服务，也不需要手动装这个 skill 的 Python 依赖。agent 会按 skill 里的说明自动启动本地服务；如果本机还没有 `wechat-download-api`，启动脚本会自动下载；服务依赖也会自动安装。

唯一需要你手动做的是：第一次启动后，按提示打开登录页，用公众号管理员微信扫码登录。

## 安装

```bash
git clone git@github.com:konglong87/wechat-download-skill.git ~/.claude/skills/wechat-download
```

如果你已经把本仓库放到别的位置，也可以链接到 Claude skill 目录：

```bash
ln -s /path/to/wechat-download-skill ~/.claude/skills/wechat-download
```

## Agent 会自动做什么

当你让 agent 下载公众号文章时，它会：

1. 检查本地 `wechat-download-api` 服务是否可用。
2. 如未启动，运行 `scripts/start_wechat_api.sh`。
3. 如本机没有 `wechat-download-api`，自动 clone 到 skill 目录下。
4. 自动安装底层服务需要的 Python 包。
5. 引导你打开 `http://localhost:8765/login.html` 扫码登录。
6. 搜索公众号，获取 `fakeid`。
7. 批量下载文章内容到本地目录。

默认端口是 `8765`。如果你已经用 upstream `wechat-download-api` 的默认端口 `5000` 启动了服务，agent 可以通过 `WECHAT_API_URL=http://localhost:5000` 使用它。

## 手动命令

通常不需要手动执行这些命令；它们主要给 agent 或排障时使用。

```bash
cd ~/.claude/skills/wechat-download

bash scripts/start_wechat_api.sh               # 启动服务，默认端口 8765
python3 scripts/download_wechat.py status      # 检查服务状态
python3 scripts/download_wechat.py search "公众号名称"
python3 scripts/download_wechat.py download "fakeid" 200 ./output
python3 scripts/download_wechat.py list "fakeid" 0 50
python3 scripts/download_wechat.py rss "fakeid"
```

## 扫码登录

下载公众号历史文章需要通过微信公众平台后台接口获取文章列表，所以需要一个微信公众号管理员账号登录。

1. 打开 `http://localhost:8765/login.html`
2. 用公众号管理员微信扫码
3. 登录成功后凭证会保存到本地 `.env`
4. 凭证通常约 4 天后过期，过期后重新扫码即可

如果你没有微信公众号管理员账号，agent 只能尝试搜索引擎、转载平台或镜像站等替代方案，覆盖率会低很多。

## 文件结构

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

## 常见问题

| 问题 | 处理方式 |
| --- | --- |
| 端口被占用 | 让 agent 换端口，或手动执行 `bash scripts/start_wechat_api.sh 9876` |
| 登录过期 | 重新打开 `http://localhost:8765/login.html` 扫码 |
| 触发微信安全验证 | 降低频率，浏览器打开提示 URL 完成验证，等待一段时间再试 |
| 部分文章下载失败 | 文章可能被删除、访问受限、是广告/图片分享，通常跳过即可 |
| `curl_cffi` 安装失败 | macOS 安装 Xcode CLT：`xcode-select --install` |

## 底层项目

本 skill 封装了 [tmwgsicp/wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)。
