---
name: wechat-download
description: Agent-first workflow for discovering lawful WeChat article URLs and archiving verified Markdown and local image galleries; users state goals in natural language and do not run project commands.
metadata:
  version: "1.4.0-dev"
---

# 微信公众号文章归档

## Agent-first workflow

Users state goals in natural language, for example “download the latest three posts from 孔小黑进城”. The Agent—not the user—runs the project commands and chooses the route.

1. Parse the account, count, output location, and any supplied article URLs.
2. Try lawful discovery adapters in order: indexed public RSS, supplied URLs, an authorized owner dashboard, optional WeRead indexing, and normal mobile-WeChat share links.
3. When a real `https://mp.weixin.qq.com/s/...` URL is available, invoke the public-page archiver internally. Verify account identity, body/gallery completeness, local files, and exit status.
4. Report downloaded, skipped, and failed items with reasons. If discovery is incomplete, ask only for the missing human action or a normally shared link; never ask the user to run terminal commands.
5. Do not promise latest-post discovery from an account name alone unless the exact discovery source and end-to-end download have been verified for that account.

The internal public archiver is `scripts/download_public.py`; it needs Python ≥3.9, does not use WeRead login or cookies, skips complete duplicates, paces batches, and stops on challenges, redirects, mismatched accounts, 403/429, or insufficient content. Image posts are archived as images plus metadata; OCR is separate.

2026-10-29 对第三方号「匿名测试公众号」的已知文章 `https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE` 已用独立公开原文入口保存 44,395 字节 Markdown；只证明**有链接时单篇可下载**，不证明仅凭账号名自动发现最新三篇。

## 可选旧路线及边界

- `download_weread.py` 保留兼容，但 eInk 列表遇 `-2041` 时保持验证熔断；**不要因为新方案运行而重置、短时重试或模拟处理验证码**。扫码登录、WeRead Web Cookie 与公众号后台会话互不通用。
- `download_rss.py` 对已收录账号可读取 Feed 的真实 `content:encoded`；无此账号或第三方服务不可达时不能伪造文件。
- 本人有管理权限的公众号后台可人工查看“近期发表/发表记录”的已发布原文链接，但不能用于任意第三方账号。移动端 [Wechat2RssScript](https://github.com/zjuerkzhang/Wechat2RssScript) 是待实机验证的开源候选，不把旧版本的成功声明当现时验收。
- 尊重版权、访问权限和平台验证；不绕过验证码、风控、付费墙，不索取 Cookie 或后台 token。输出目录保留归档，临时研究文件和截图验收后清理。

```bash
python3 scripts/download_public.py url 'https://mp.weixin.qq.com/s/EXAMPLE_ARTICLE' ./wechat_downloads/匿名测试公众号 --account '匿名测试公众号'
python3 scripts/download_public.py batch links.txt ./wechat_downloads/匿名测试公众号 --account '匿名测试公众号'
python3 scripts/download_rss.py search '小众软件'
python3 -m unittest discover -s tests -v
```
