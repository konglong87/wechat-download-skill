# wechat-download-skill

通过**微信读书扫码登录**，搜索微信公众号、列出文章并将可读取的正文保存为 Markdown 的 Agent Skill／命令行工具。已有文章链接可直接下载；公开 RSS 是无需登录的备用路线，旧公众号后台接口只保留兼容。

> **实测状态（2026-10-28）**：用户提供的[这篇文章](https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE)通过微信读书路线保存为 40,490 字节 Markdown，正文约 19,832 字符，并检查了开头、中段和结尾。其他文章有时只返回页面外壳或“正文不足”，**不能保证任意公众号、全部历史文章或每篇完整正文**。脚本会拒绝明显的空壳，而不是把它报为下载成功；仍需逐篇验收。

[English README](README.en.md)

## 安装与首次登录

macOS／Linux；需要 Python **≥3.9**、Node.js **≥22.13.0** 和 npm。无需公众号后台管理员权限；需要本人已开通微信读书的微信账号扫码。

```bash
git clone https://github.com/konglong87/wechat-download-skill.git
cd wechat-download-skill
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login   # 用手机微信扫码并确认
python3 scripts/download_weread.py status  # 检查 auth.status 为 authenticated
```

安装脚本将固定版本 `weread-omni@0.1.2` 放在 `~/.local/share/wechat-download-skill/weread-omni/`，不修改全局 npm 包。登录凭证由该 CLI 保存在用户目录，本项目不读取或提交 Cookie；手机微信读书的登录设备页可能显示 **BOOX**。微信读书登录与公众号后台登录互不通用。

### 已知文章链接：直接下载

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads
# 需要跳过 CLI 缓存、重新从上游抓取时：
python3 scripts/download_weread.py --refresh url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads
```

将示例链接替换为自己的 `https://mp.weixin.qq.com/s/...` 文章链接。成功时打印 `.md` 路径与字节数；请打开文件检查实际正文。上面的成功案例是特定日期的实测，**不是该链接今后总能访问的保证**。

### 只有公众号名称：先查索引，再小批量下载

```bash
python3 scripts/download_weread.py search '匿名测试公众号'
# 从搜索结果的 bookInfo.bookId 取得真实 MP_WXS_<数字>，替换下方示意 ID：
python3 scripts/download_weread.py list MP_WXS_1234567890 0 5
python3 scripts/download_weread.py download MP_WXS_1234567890 5 ./wechat_downloads
```

先试 1～5 篇并读回文件，再决定是否增加数量；默认请求 200 篇、单次最多 1,000 篇，**不等于公众号全量历史**。微信读书 ID 不是旧公众号后台的 `fakeid`。脚本不自动关注公众号；若确需关注，请由用户在微信读书 App 中操作。

## 输出与失败处理

- 每篇成功文章保存一个带原文链接、公众号名和发布时间的 `.md` 文件；已保存的文章跳过。**图片不下载到本地**，如上游保留图片链接，仅在正文中引用远程地址。
- 正文缺失或仅含“原创／阅读原文／不喜欢”等页面按钮时返回错误，不生成伪正文；批量下载记录失败项到 `failures.json` 并返回非零退出码。核对成功数、失败数和实际文件，不要把“搜索成功”当成“全文下载成功”。
- 微信读书接口可能临时返回 `-2041`；本次测试中稍后重试搜索和列表恢复，手机 App **没有**出现单独的验证入口。遇到风控请停止高频请求，之后再试，勿绕过平台验证。
- 上游可能标记 `completeness=unverified`。即使正文看起来完整，也无法保证与微信原文逐字一致；已删、受限、付费文章及部分公开文章可能无法读取。只归档自己有权访问和使用的内容。

## 免登录备用：公开 RSS

如果无法登录微信读书，或某篇文章在微信读书不可读，可先查公开目录中是否收录该公众号：

```bash
python3 scripts/download_rss.py search '小众软件'
python3 scripts/download_rss.py list 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml'
python3 scripts/download_rss.py download 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml' 1 ./wechat_downloads
```

这条路线从第三方 Feed 的 `content:encoded` 保存近期文章为 `.txt`，不请求受限的微信原文页。2026-10-28 曾真实保存并读回“小众软件”正文；随后该 Feed 也发生过 TLS 超时／响应不完整。**仅覆盖目录收录号、Feed 当前提供的近期文章，且依赖第三方服务可用性**；不是任意链接的通用兜底。

## Agent Skill 与维护

克隆后可直接在项目目录执行上述脚本；若在支持 Skill 的 Agent 中使用，将克隆后的目录命名为 `wechat-download`（与 [`SKILL.md`](SKILL.md) 的 `name` 一致）并放入该 Agent 的 skills 目录；例如 Codex 可放在 `~/.codex/skills/wechat-download/`。然后即可用“下载某公众号最近 5 篇”之类的任务调用。需要自己指定已安装 CLI 时设置 `WEREAD_CLI=/path/to/weread-omni`；多账号可设置 `WEREAD_ACCOUNT=alias`。

```bash
python3 -m unittest discover -s tests -v
```

实现：`download_weread.py → weread_client.py → [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni)（MIT）→ 微信读书文章索引与公开原文`。公开 RSS 为独立备用适配器。旧 `download_wechat.py`／`start_wechat_api.sh` 兼容 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)，但旧后台文章列表在实测中返回 `ret=200013, freq control`，**不推荐作为批量下载入口**。不复制第三方源码，不绕过验证码或访问限制。
