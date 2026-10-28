---
name: wechat-download
description: Discover WeChat account posts via WeRead; download accessible full bodies via eInk, optional authorized Web, or exact-article public RSS, then verify real Markdown files.
metadata:
  version: "1.4.0-dev"
---

# 微信公众号文章下载

## 路由与边界

1. **默认微信读书**：`download_weread.py → weread_client.py → weread-omni@0.1.2 (MIT) → 微信读书文章索引和原文链接`。已实测扫码登录、搜索、列表和用户指定链接的正文落盘（40,490 字节，约 19,832 字符，2026-10-28）。同号最新三篇（2026-10-28）实测 `0/3`，均为 `SOURCE_CONTENT_INSUFFICIENT`；逐篇验收，不保证最新全文或全量历史。
2. **可选网页授权＋自动 RSS 兜底**：主命令正文读取失败时，对暂时性错误最多重试 3 次（额外于首次），2／4／8 秒退避并强制刷新缓存；正文不足时以一次无跳转 `HEAD` 探测原文验证页并终止无效重试，明确频控也不重试。若用户自行授权微信读书网页登录并执行 `web-cookie`，先尝试 `/web/mp/content`；仍失败才以公众号准确名称查询公开 RSS 目录，并按原文文章标识精确匹配 Feed 项，保存带第三方来源提示的 `.md`。独立 `download_rss.py` 则从公开 Feed 保存 `.txt`。第三方源可能超时，不可保证任意文章。
3. **旧兼容入口**：`download_wechat.py → wechat-download-api → 微信公众平台后台`。列表实测 `ret=200013, freq control`，不推荐批量使用。登录或健康检查通过不等于文章下载成功。

尊重版权、内容权限及平台验证。不得绕过验证码、风控、付费墙；不要声称能下载某公众号的所有历史文章。

## Agent 执行流程

1. 在项目目录检查 Python ≥3.9、Node.js ≥22.13.0、npm；优先使用 `WEREAD_CLI`、PATH 或默认安装路径的 `weread-omni`，缺失则运行 `bash scripts/install_weread_cli.sh`。已登录用户不要重复要求扫码。
2. 运行 `python3 scripts/download_weread.py status`。未登录才运行 `python3 scripts/download_weread.py login`，把二维码呈现给用户本人扫码确认；可能显示 BOOX 设备。eInk 认证信息属于上游 CLI；不要读取、输出或提交凭证。可选 Web 通道与 eInk 登录态不同，只有用户自行授权并在本机隐藏提示保存 `0600` Cookie 文件后才能启用，绝不在聊天中索取。
3. **已给文章链接**：运行 `python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/...' ./wechat_downloads`；怀疑缓存时在子命令前加 `--refresh`。核对退出码、文件大小、开头/中段/结尾及原文链接；仅有作者或“阅读原文／不喜欢”不算正文。
4. **仅给公众号名称**：先 `search '名称'`，从 `bookInfo.bookId` 确认真实 `MP_WXS_<数字>`（不能使用旧 `fakeid`）；再 `list ID 0 5`、`download ID 1 ./wechat_downloads`，确认真实落盘后才逐步增大数量。默认 200、最多 1,000 篇；这是请求上限，不是历史覆盖承诺。
5. 若用户已在 `weread.qq.com` 网页登录且愿意尝试实验通道，可指引其在本机执行 `python3 scripts/download_weread.py web-cookie`，从浏览器开发者工具复制该站点 Cookie 值到隐藏终端提示；程序仅向固定微信读书 Web 正文接口请求，失败仍按相同原文 URL 尝试 RSS，不能承诺成功。2026-10-28 无 Web 会话时实测 `errCode=-2010`，最新三篇仍为 `0/3`。
6. 阅读 `.md` 内容，核对 `failures.json`、实际文件数量与错误。若上游未识别公众号名称且用户已明确给出准确名称，可在 `url` 或 `download` 后添加 `--rss-account '名称'` 供自动兜底使用；RSS 必须匹配同一篇文章，不能替换成“相似”文章。空正文、页面外壳、空列表、0 文件、`-2041` 或 `SOURCE_CONTENT_INSUFFICIENT` 均不可报成功。`-2041` 曾在稍后重试恢复，不可断言手机 App 一定有二次验证入口；遇频控停止高频重试。
7. 微信读书不可用或文章不可读时，若用户给出**公众号名称**，可 `download_rss.py search '名称'`；命中后使用返回的 Feed URL `list URL`、`download URL 1 ./wechat_downloads`，只将真实 `content:encoded` 文件称为已下载。第三方源超时、目录缺号、正文不足时如实报告，不生成伪文件。
8. 用户提出定时任务时，只有在其指定目标和周期后才配置 Agent 外部调度；先实测目标号最近若干篇。持久化输出目录，报告新增、跳过、失败和退出码；失败不可报“无新文”。当前「匿名测试公众号」仅能列出新文，最新三篇正文均失败，不得宣称可稳定定时下载该号全文。
9. 不自动关注公众号，不调用订阅写接口，除非用户明确授权；输出图片链接可能仍是远程地址。真实下载产物保留，临时二维码、抓取中间文件与失败测试目录在验收后清理；用户家目录中的登录凭证不得清除。

## 常用命令

```bash
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login
python3 scripts/download_weread.py status
# 仅本人已在 weread.qq.com 网页登录且愿意启用时：
# python3 scripts/download_weread.py web-cookie
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads
# 当上游不能识别公众号名时：url ... ./wechat_downloads --rss-account '准确名称'
python3 scripts/download_weread.py search '匿名测试公众号'
# 用搜索结果 bookInfo.bookId 替换示意 ID：
python3 scripts/download_weread.py list MP_WXS_1234567890 0 5
python3 scripts/download_weread.py download MP_WXS_1234567890 5 ./wechat_downloads
python3 scripts/download_rss.py search '小众软件'
python3 -m unittest discover -s tests -v
```

`WEREAD_CLI=/path/to/weread-omni` 指定已有 CLI，`WEREAD_ACCOUNT=alias` 选账号。上游微信读书 `completeness=unverified` 时，长正文也不能证明和微信原文逐字相同；以实际文件与中段/结尾验收为准。
