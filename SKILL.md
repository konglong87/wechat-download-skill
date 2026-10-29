---
name: wechat-download
description: Archive legitimately obtained public WeChat article URLs as verified Markdown and local image galleries without WeRead; discover links only through lawful public feeds or user sharing.
metadata:
  version: "1.4.0-dev"
---

# 微信公众号文章归档

## 当前首选路线

1. **输入是原文链接**：用户从公众号文章的正常分享操作或已验证的公开 Feed 得到 `https://mp.weixin.qq.com/s/...`。执行 `python3 scripts/download_public.py url '原文链接' ./wechat_downloads/账号 --account '准确名称'`。批量时在 UTF-8 文本中每行放一条链接，运行 `python3 scripts/download_public.py batch links.txt ./wechat_downloads/账号 --account '准确名称'`。仅需 Python ≥3.9，不调用微信读书、不读登录态或 Cookie。
2. **只给账号名**：先检查 `download_rss.py search '准确名称'` 的公开目录（只覆盖收录账号），或用户可正常分享的原文链接。第三方标题目录及 ReadGZH 缓存可能不全或不含原文 URL；不得把标题、摘要、旧文当作最新文章。若没有可验证的最近原文 URL，明确报告自动发现未完成，向用户索取正常分享链接；不要臆造链接。
3. **验收**：检查命令退出码、文件来源/账号/发布时间、普通正文开头/中段/结尾、图片分享本地全部原图。验证页、账号不符、仅摘要、图片缺失都不是成功。批量已完整存档的 URL 自动跳过；遇验证或访问拒绝即停，不自动重试。用户未指定周期时不配置定时任务；要承诺无人值守，必须先实测指定账号最近若干篇的发现与落盘端到端。

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
