---
name: wechat-download
description: Download authorized WeChat official-account articles via QR-authenticated WeRead. Search accounts, list recent articles, and verify each saved Markdown body; use public RSS only as a limited login-free fallback.
metadata:
  version: "1.3.0"
---

# 微信公众号文章下载

## 路由与边界

1. **默认微信读书**：`download_weread.py → weread_client.py → weread-omni@0.1.2 (MIT) → 微信读书文章索引和原文链接`。已实测扫码登录、搜索、列表和用户指定链接的正文落盘（40,490 字节，约 19,832 字符，2026-10-28）。同号最新三篇（2026-10-28）实测 `0/3`，均为 `SOURCE_CONTENT_INSUFFICIENT`；逐篇验收，不保证最新全文或全量历史。
2. **免登录备用**：`download_rss.py → 公开 Wechat2RSS 目录/Feed → content:encoded → .txt`。仅适用于目录收录号的近期 Feed；实测曾成功下载，但第三方源也发生过超时/响应不完整。不能当作任意文章 URL 的替代品。
3. **旧兼容入口**：`download_wechat.py → wechat-download-api → 微信公众平台后台`。列表实测 `ret=200013, freq control`，不推荐批量使用。登录或健康检查通过不等于文章下载成功。

尊重版权、内容权限及平台验证。不得绕过验证码、风控、付费墙；不要声称能下载某公众号的所有历史文章。

## Agent 执行流程

1. 在项目目录检查 Python ≥3.9、Node.js ≥22.13.0、npm；优先使用 `WEREAD_CLI`、PATH 或默认安装路径的 `weread-omni`，缺失则运行 `bash scripts/install_weread_cli.sh`。已登录用户不要重复要求扫码。
2. 运行 `python3 scripts/download_weread.py status`。未登录才运行 `python3 scripts/download_weread.py login`，把二维码呈现给用户本人扫码确认；可能显示 BOOX 设备。认证信息属于上游 CLI，不读取、输出、复制或提交 Cookie。
3. **已给文章链接**：运行 `python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/...' ./wechat_downloads`；怀疑缓存时在子命令前加 `--refresh`。核对退出码、文件大小、开头/中段/结尾及原文链接；仅有作者或“阅读原文／不喜欢”不算正文。
4. **仅给公众号名称**：先 `search '名称'`，从 `bookInfo.bookId` 确认真实 `MP_WXS_<数字>`（不能使用旧 `fakeid`）；再 `list ID 0 5`、`download ID 1 ./wechat_downloads`，确认真实落盘后才逐步增大数量。默认 200、最多 1,000 篇；这是请求上限，不是历史覆盖承诺。
5. 阅读 `.md` 内容，核对 `failures.json`、实际文件数量与错误。空正文、页面外壳、空列表、0 文件、`-2041` 或 `SOURCE_CONTENT_INSUFFICIENT` 均不可报成功。`-2041` 曾在稍后重试恢复，不可断言手机 App 一定有二次验证入口；遇频控停止高频重试。
6. 微信读书不可用或文章不可读时，若用户给出**公众号名称**，可 `download_rss.py search '名称'`；命中后使用返回的 Feed URL `list URL`、`download URL 1 ./wechat_downloads`，只将真实 `content:encoded` 文件称为已下载。第三方源超时、目录缺号、正文不足时如实报告，不生成伪文件。
7. 用户提出定时任务时，只有在其指定目标和周期后才配置 Agent 外部调度；先实测目标号最近若干篇。持久化输出目录，报告新增、跳过、失败和退出码；失败不可报“无新文”。当前「匿名测试公众号」仅能列出新文，最新三篇正文均失败，不得宣称可稳定定时下载该号全文。
8. 不自动关注公众号，不调用订阅写接口，除非用户明确授权；输出图片链接可能仍是远程地址。真实下载产物保留，临时二维码、抓取中间文件与失败测试目录在验收后清理；用户家目录中的登录凭证不得清除。

## 常用命令

```bash
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login
python3 scripts/download_weread.py status
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads
python3 scripts/download_weread.py search '匿名测试公众号'
# 用搜索结果 bookInfo.bookId 替换示意 ID：
python3 scripts/download_weread.py list MP_WXS_1234567890 0 5
python3 scripts/download_weread.py download MP_WXS_1234567890 5 ./wechat_downloads
python3 scripts/download_rss.py search '小众软件'
python3 -m unittest discover -s tests -v
```

`WEREAD_CLI=/path/to/weread-omni` 指定已有 CLI，`WEREAD_ACCOUNT=alias` 选账号。上游微信读书 `completeness=unverified` 时，长正文也不能证明和微信原文逐字相同；以实际文件与中段/结尾验收为准。
