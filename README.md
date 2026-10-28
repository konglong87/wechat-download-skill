# wechat-download-skill

通过**微信读书扫码登录**，搜索微信公众号、列出文章并将可读取的正文保存为 Markdown 的 Agent Skill／命令行工具。已有文章链接可直接下载；可选的微信读书**网页授权正文通道**用于公开原文受限时尝试读取，公开 RSS 是无登录备用路线。旧公众号后台接口只保留兼容。

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

安装脚本将固定版本 `weread-omni@0.1.2` 放在 `~/.local/share/wechat-download-skill/weread-omni/`，不修改全局 npm 包。eInk 登录凭证由该 CLI 保存在用户目录，本项目默认不读取 Cookie；仅用户显式启用网页通道时，才读取本人提供的单独 Web Cookie 私有文件，绝不打印或提交；手机微信读书的登录设备页可能显示 **BOOX**。微信读书登录与公众号后台登录互不通用。

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
- 正文缺失或仅含“原创／阅读原文／不喜欢”等页面按钮且 RSS 也无可用原文时返回错误，不生成伪正文；批量下载记录失败项到 `failures.json` 并返回非零退出码。核对成功数、失败数和实际文件，不要把“搜索成功”当成“全文下载成功”。
- 微信读书接口可能临时返回 `-2041`；本次测试中稍后重试搜索和列表恢复，手机 App **没有**出现单独的验证入口。遇到风控请停止高频请求，之后再试，勿绕过平台验证。
- 上游可能标记 `completeness=unverified`。即使正文看起来完整，也无法保证与微信原文逐字一致；已删、受限、付费文章及部分公开文章可能无法读取。只归档自己有权访问和使用的内容。

## 自动重试与 RSS 兜底

- 读取文章正文失败时，若属于**正文不足、连接超时或临时服务错误**，首次请求后最多再重试 **3 次**，间隔 **2／4／8 秒**；重试强制绕开 CLI 缓存。正文不足时仅做一次有限的公开原文 `HEAD` 探测：若明确重定向到微信验证页，立即停止无效重试，不跟随或保存验证令牌。`-2041`、频控、验证码或明确“页面被拦截”也不高频重试。
- 主路线失败后，若用户**自行配置网页授权**，先尝试微信读书 Web 正文；仍失败才按同一篇原文使用 RSS。若微信读书响应给出了公众号名称，自动查询公开 RSS 目录；找不到名称时，可用 `--rss-account '公众号准确名称'` 显式指定。只有 RSS Feed 中**同一篇原文链接**（匹配短链接，或 `__biz`／`mid`／`idx`／`sn` 四个文章标识）存在且正文足够长，才保存为 `.md`；文件注明“内容渠道：公开 RSS（第三方）”。**不会拿同名或邻近文章冒充目标文章**。
- 目标号未收录、Feed 超时、没有这篇文章或正文不足时，仍返回非零退出码，批量命令记录到 `failures.json`。还没有获得文章 URL 的搜索/列表失败不能精确匹配 RSS 单篇，仍需人工确认目标后使用独立 RSS 命令。

```bash
# 微信读书无法自动识别公众号名称时，显式告诉兜底路线：
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads --rss-account '公众号准确名称'
```

2026-10-28 再测「匿名测试公众号」最新三篇：旧版第 1、3 篇各执行首次请求 + 3 次退避重试，第 2 篇明确被拦截只请求一次；三篇原文独立 HTTP 检查均重定向至微信验证页。新版本会识别验证重定向并停止无效重试。RSS 目录未收录该号，**仍是 0/3**。网页正文接口在没有网页会话时返回 `errCode=-2010`，尚待本人网页登录后真实验收。另以已收录的「小众软件」测试真实兜底时，第三方 RSS 当时发生 TLS 握手超时；所以兜底机制可自动执行，但**不保证第三方源随时可用**。单元测试覆盖 RSS 精确匹配、退避、成功保存、风控停机和失败结果。

## 可选：微信读书网页授权正文通道（实验性）

[社区项目 we-mp-rss 的实现](https://github.com/rachelos/we-mp-rss/blob/main/core/wx/model/weread_mp.py)提示另一个微信读书 Web 正文接口 `/web/mp/content?reviewId=...`。这与 `weread-omni` 的 eInk 扫码登录**不是同一登录态**。实测无网页登录时返回 `errCode=-2010`（用户不存在）；目前尚未在本项目验证“匿名测试公众号”最新三篇能否由**真实已授权 Web 会话**读取，不能将这项改动称为已下载成功。此接口非正式公开 API，可能随时变化。

1. 在自己的浏览器访问 `https://weread.qq.com`，自行完成网页登录，确认本人可在网页中正常阅读目标文章。不要把 Cookie、二维码或验证码发给 Agent／聊天窗口。
2. 如愿意启用此实验通道，在浏览器开发者工具 **Network** 中选择 `weread.qq.com` 的同源请求，复制 **Request Headers → Cookie 的值**（不要复制其他站点的 Cookie）；于本机交互式终端执行 `python3 scripts/download_weread.py web-cookie`，在隐藏输入提示粘贴并回车。文件存于 `~/.local/share/wechat-download-skill/weread-web.cookie`，权限 `0600`，项目 `.gitignore` 忽略 `*.cookie`。请将它视作登录密钥，不要分享到 Issue 或提交到 Git。
3. 再运行下列命令。程序只向固定 `https://weread.qq.com/web/mp/content` 发送该 Cookie，不跟随重定向；仅在识别到非空正文时写 Markdown。无登录、响应是验证页、正文太短时会继续按原文精确匹配 RSS，最终失败仍返回非零状态。

```bash
python3 scripts/download_weread.py --refresh download MP_WXS_1234567890 3 ./wechat_downloads/匿名测试公众号 --rss-account '匿名测试公众号'
# 如需另选私有文件：把 --web-cookie-file /安全目录/weread-web.cookie 放在 download 子命令前
```

凭证过期请在网页重新登录并再次执行 `web-cookie`；想禁用此通道可自行移走该私有文件。**不绕过验证、风控或付费权限**；先验收三篇实际正文与文件，再安排无人值守定时下载。

## 定时检查：目前仅能可靠发现标题，不保证下载正文

Agent 可以在已有登录态和**持久化输出目录**下定期运行 `status`、`list ID 0 10`，再调用 `download ID 10 ./wechat_downloads/目标号`，报告实际新增 `.md`、跳过和失败数；若命令非零退出，不能把本次巡检标记为成功或“没有新文章”。检查数量要覆盖两次运行间可能新增的文章。Codex、Claude 等 Agent 的定时机制由用户自行配置，本项目不安装后台任务；只有用户显式执行 `web-cookie` 时才在个人目录保存独立的网页会话密钥。

**2026-10-28 对「匿名测试公众号」最新三篇的实际测试：列表可返回标题，但三篇均报 `SOURCE_CONTENT_INSUFFICIENT`，新增正文文件 `0/3`；公开 RSS 目录也未收录该号。**因此这条路线目前能作为新文**索引监测**的基础，但**不能向用户承诺该号可无人值守定时下载最新全文**。当上游原文可读时，已有单篇实测成功；需按目标号、按文章复测。

## 免登录备用：公开 RSS

给定文章链接且已知公众号名称时，上述主命令会自动尝试 RSS 兜底；也可以单独查询公开目录，或在无法登录微信读书时直接使用 RSS：

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

实现：`download_weread.py → weread_client.py → [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni)（MIT）→ 微信读书文章索引与公开原文`。可选 `weread_web_body.py` 只使用用户授权 Web 会话，公开 RSS 为独立备用适配器。旧 `download_wechat.py`／`start_wechat_api.sh` 兼容 [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api)，但旧后台文章列表在实测中返回 `ret=200013, freq control`，**不推荐作为批量下载入口**。不复制第三方源码，不绕过验证码或访问限制。
