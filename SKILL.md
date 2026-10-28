---
name: wechat-download
description: Download, archive, or search WeChat official-account (公众号) articles, using public RSS for indexed accounts and WeRead for broader discovery after the old MP history endpoint stopped working.
version: 1.2.0
---

# 微信公众号文章下载

## 架构与边界

- **已实测免登录备选**：`download_rss.py → 公开 Wechat2RSS 目录/Feed → content:encoded → 本地 .txt`。只适用于目录收录的号与 Feed 当前提供的近期文章；第三方内容未独立核对全文完整度。2026-10-28 实测一篇正文真实落盘、读回和浏览器截图均通过。
- **待真人扫码验证的扩展路线**：`download_weread.py → weread_client.py → weread-omni@0.1.2 (MIT) → 微信读书索引/原文`。不能把旧公众号后台登录当成微信读书登录。
- **旧路由**：`download_wechat.py → wechat-download-api → 微信公众平台后台` 保留兼容；文章列表实测 `ret=200013, freq control`，不要依赖其批量下载。登录、健康检查或搜索成功不等于列表成功。

所有路线都必须尊重内容权限、版权和平台验证；不得绕过验证码或风控。公开 RSS 只读取目录和 HTTPS feed，不抓取验证页。

## Agent 执行流程

1. **优先尝试公开 RSS（目标已被收录时）**：`python3 scripts/download_rss.py search '名称'`。找到后以返回的 feed URL 执行 `list URL` 和 `download URL 1 ./wechat_downloads`，确认真实正文和文件。仅把 Feed 中的 `content:encoded` 称为“已下载”；不承诺全历史。目录缺号或内容不足，转下一步。此路线只需 Python >=3.9，无需扫码。
2. 检查 Node.js >=22.13.0 与 Python >=3.9。优先寻找 `WEREAD_CLI`、PATH 中的 `weread-omni` 或默认安装路径；缺失则运行 `bash scripts/install_weread_cli.sh`。该脚本只安装固定版本，不需要公众号后台服务。
3. 运行 `python3 scripts/download_weread.py status`。如未登录，运行 `python3 scripts/download_weread.py login` 并将二维码呈现给用户，让**用户亲自**用微信读书账号扫码、确认和完成可能的二次验证。切勿读取、打印或提交 Cookie。原公众号后台扫码不能代替微信读书登录。
4. 已给文章链接时，直接运行 `python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/...' ./wechat_downloads`，检查退出码及 `.md` 文件大小与正文。
5. 仅给公众号名称时，先 `python3 scripts/download_weread.py search '名称'`，核对返回的公众号身份，取得微信读书 `MP_WXS_<数字>`。不要把旧 `fakeid` 当微信读书 ID。
6. 运行 `python3 scripts/download_weread.py list MP_WXS_1234567890 0 10`；确认真实文章列表，再 `python3 scripts/download_weread.py download MP_WXS_1234567890 20 ./wechat_downloads`。默认下载数 200，最大 1,000；首先以小批量验收，再扩大数量。
7. 验证目标目录的 `.md` 文件确有正文，并检查 `failures.json`、退出码与实际数量。遇到频控/验证时停下来；不要把空列表或 0 文件当作成功。图片 URL 暂不本地化。

**关注公众号是写操作**：不要为了取列表自动调用 `weread-omni public-accounts subscribe`。若目标账号需要关注，先让用户确认并在微信读书 App 内操作或明确授权订阅。搜索或列表不要求默认关注；优先测试只读路线。

## 命令

```bash
python3 scripts/download_rss.py search '公众号名称'
python3 scripts/download_rss.py list 'https://wechat2rss.xlab.app/feed/<40位哈希>.xml'
python3 scripts/download_rss.py download 'https://wechat2rss.xlab.app/feed/<40位哈希>.xml' 1 ./wechat_downloads
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login
python3 scripts/download_weread.py status
python3 scripts/download_weread.py search '公众号名称'
python3 scripts/download_weread.py list MP_WXS_1234567890 0 10
python3 scripts/download_weread.py download MP_WXS_1234567890 20 ./wechat_downloads
python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/ARTICLE' ./wechat_downloads
```

CLI 可用 `WEREAD_CLI=/path/to/weread-omni` 指定；多账号用 `WEREAD_ACCOUNT=alias`。`--refresh` 放在子命令前，可强制从上游重新抓取。用户的微信读书凭证由上游 CLI 在其配置目录内管理，本 skill 不另建凭证数据库。

## 验证与保留

- 单元测试：`python3 -m unittest discover -s tests -v`。
- RSS 真实验收检查目录命中、Feed 新鲜度、`content:encoded`、实际文件和截图；微信读书真实验收则需扫码后的账号状态、搜索、列表与文件读回。缺少真人扫码或遇验证时，明确说出未验证的环节。
- 测试中间下载目录可清理；真实凭证在用户家目录，不要删除、输出或上传。旧服务启动时只能绑定到 `127.0.0.1`，不可把未鉴权的管理接口暴露给局域网。
