# wechat-download

一个用于下载微信公众号文章的 agent skill。**已实测的公开 RSS 路线**可免登录下载收录号的近期正文；**微信读书路线**已完成真人扫码测试，但当前账号的搜索、列表遭遇官方客户端真人验证 `-2041`；已知文章链接返回的只有页面外壳，不能当作正文下载成功。旧的微信公众平台后台接口保留为兼容模式，但文章列表在 2026 年的实际测试中返回 `ret=200013, freq control`，不要把服务健康检查当作批量下载成功。

English: [README.en.md](README.en.md)

## 免登录：公开 RSS（已完成真实下载验收）

先查公开目录；找到后使用返回的 feed URL，避免重复检索：

```bash
python3 scripts/download_rss.py search "小众软件"
python3 scripts/download_rss.py list 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml'
python3 scripts/download_rss.py download 'https://wechat2rss.xlab.app/feed/3261d5a75cfef238650a2cabd4bbf99669c2f334.xml' 1 ./wechat_downloads
```

此路由只接受该站固定格式的 `https://wechat2rss.xlab.app/feed/<40位哈希>.xml`；按名称搜索仅覆盖公开目录收录号，直接使用 RSS 的 `content:encoded` 正文保存为 `.txt`，**不请求受限的微信原文页面**，不需要微信读书或公众号后台登录。2026-10-28 实测「小众软件」源提供 20 篇、最近更新至 10 月 27 日；1 篇文章实际写入 3,223 字节并读回。RSS 收录范围、更新频率和正文完整度均由第三方决定，**不保证任意公众号、全量历史或与原文逐字相同**。图片仅保留远程 URL。

若目录无目标号或需更多历史，再尝试下方微信读书路线。

## 快速开始

安装 skill 后，在 Claude Code / agent 里说“下载 XXX 公众号最近 20 篇文章”。若公开 RSS 目录已收录该号，无需安装或登录；否则可尝试微信读书路线，由 Agent 安装开源 CLI，并请你**用已开通微信读书的微信号扫码登录一次**。微信读书与公众号后台是两套独立登录态。

手动执行（macOS / Linux，Node.js **>=22.13.0**，Python **>=3.9**）：

```bash
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login
python3 scripts/download_weread.py status
python3 scripts/download_weread.py search "人民日报"
# 搜索结果中确认 MP_WXS_<数字>，不可使用旧的 fakeid
python3 scripts/download_weread.py list MP_WXS_1234567890 0 10
python3 scripts/download_weread.py download MP_WXS_1234567890 20 ./wechat_downloads
```

已有文章链接时，不必搜索公众号：

```bash
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads
```

也可以设置 `WEREAD_CLI=/path/to/weread-omni` 使用你已有的 CLI，或用 `WEREAD_ACCOUNT=other` 指定已登录账号。`--refresh` 可强制重新抓取而非使用微信读书 CLI 的本地缓存。

## 微信读书实现与输出（已实测，目前受阻）

```text
scripts/download_weread.py → scripts/weread_client.py → weread-omni (MIT) → 微信读书接口
                                                  ↘ 微信原文链接与正文
```

- `install_weread_cli.sh` 将固定版本的 `weread-omni@0.1.2` 安装到 `~/.local/share/wechat-download-skill/weread-omni/`，不全局覆盖 npm 包；认证信息由该 CLI 保存在自己的用户配置目录，skill 不读取或输出 Cookie。
- `search` 通过微信读书搜索公众号；`list` 和 `download` 使用 `MP_WXS_<数字>`，首次列表请求不带 offset，后续按微信读书游标分页；最多处理 1,000 篇，默认 200 篇。
- 仅在正文通过最低限度的内容检查后才输出每篇一个 `.md`；上游把仅含作者/“阅读原文”等按钮的页面标为 `readable` 时，适配器会拒绝保存（2026-10-28 真人扫码后实际发现并修复的误报）。已保存的文件跳过。**图片暂保留远程 URL，不下载图片文件。**部分失败写入 `failures.json`，命令返回非零退出码；遇到频控/验证会停止，避免连续触发风控。
- 不会自动关注公众号。若目标号必须先在微信读书关注，请在微信读书客户端操作，或者明确授权后再使用 `weread-omni public-accounts subscribe`。

2026-10-28 端到端实测：微信读书扫码登录和 `status` 认证成功；「小众软件」搜索 `/store/search` 与已知账号 ID 的文章列表 `/mp/chapters` 均返回 `-2041`，提示需要在官方客户端完成真人验证。已知文章链接的 `read-article` 返回 `status=readable` 但 `completeness=unverified`，仅 21 字“原创/作者/阅读原文/不喜欢”；强制刷新及第二篇均一样，原文页直接请求也返回验证页面。本项目不会绕过验证，不能声称该路线目前可自动下载完整正文。若你在官方微信读书 App 中完成提示的验证，可再重试；目前已实测可用的范围仅是上方公开 RSS 收录号的近期内容。

> 微信读书使用非公开接口，列表是它持有的文章索引，不保证包含目标公众号的全部历史、已删文章或付费全文。登录可能需要微信读书 App 端二次验证；请正常完成，勿绕过验证。仅归档你有权访问和使用的内容。

## 旧接口（仅供兼容）

原 `scripts/start_wechat_api.sh` 和 `scripts/download_wechat.py` 仍可用于排障，且在已登录情况下可用 `/api/article` 处理**已知链接**。但是其按 fakeid 获取文章列表的微信后台入口在当前测试中受阻，不再作为推荐下载方式。旧批量脚本现在会对列表错误或空列表返回非零退出码，不会伪报成功。

本项目保留对 [tmwgsicp/wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) 的兼容；新的微信读书路线调用 [teng-lin/weread-omni](https://github.com/teng-lin/weread-omni)（MIT），未复制其源码。
