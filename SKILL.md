---
name: wechat-download
description: Discover WeChat account posts via WeRead; download accessible full bodies via eInk, optional authorized Web, or exact-article public RSS, then verify real Markdown files.
metadata:
  version: "1.4.0-dev"
---

# 微信公众号文章下载

## 路由与边界

1. **默认微信读书**：`download_weread.py → weread_client.py → weread-omni@0.1.2 (MIT) → 微信读书文章索引和原文链接`。已实测扫码登录、搜索、列表和用户指定链接的正文落盘（40,490 字节，约 19,832 字符，2026-10-28）。同号最新三篇（2026-10-28）逐篇验收：第二篇保存 42,669 字节／17,671 字符普通正文；第一、三篇是 `item_show_type=8` 图片分享，分别下载 7／8 张原图及摘要。**3/3 篇归档，但只有一篇是纯文本全文，另两篇图片内文字尚未 OCR。**
2. **可选网页授权＋自动 RSS 兜底**：主命令正文读取失败时，对暂时性错误最多重试 3 次（额外于首次），10／30／90 秒退避并强制刷新缓存；不能用独立 `HEAD` 验证跳转判断正文：可刷新的成功旧文也会返回该跳转。明确频控不重试。CLI 失败后，`wechat_page_body.py` 一次性请求正常公开原文，普通文章只从可见正文容器或足够长的 JS 正文提取内容；图片分享从 `picture_page_info_list` 下载全部原图，保留摘要并在 Markdown 相对引用，缺一张图也不报成功；拒绝仅有摘要和验证重定向；若用户自行授权微信读书网页登录并执行 `web-cookie`，再尝试 `/web/mp/content`；仍失败才以公众号准确名称查询公开 RSS 目录，并按原文文章标识精确匹配 Feed 项，保存带第三方来源提示的 `.md`。独立 `download_rss.py` 则从公开 Feed 保存 `.txt`。第三方源可能超时，不可保证任意文章。
3. **旧兼容入口**：`download_wechat.py → wechat-download-api → 微信公众平台后台`。列表实测 `ret=200013, freq control`，不推荐批量使用。登录或健康检查通过不等于文章下载成功。

尊重版权、内容权限及平台验证。不得绕过验证码、风控、付费墙；不要声称能下载某公众号的所有历史文章。

## Agent 执行流程

1. 在项目目录检查 Python ≥3.9、Node.js ≥22.13.0、npm；优先使用 `WEREAD_CLI`、PATH 或默认安装路径的 `weread-omni`，缺失则运行 `bash scripts/install_weread_cli.sh`。已登录用户不要重复要求扫码。
2. 运行 `python3 scripts/download_weread.py status`。未登录才运行 `python3 scripts/download_weread.py login`，把二维码呈现给用户本人扫码确认；可能显示 BOOX 设备。eInk 认证信息属于上游 CLI；不要读取、输出或提交凭证。可选 Web 通道与 eInk 登录态不同，只有用户自行授权并在本机隐藏提示保存 `0600` Cookie 文件后才能启用，绝不在聊天中索取。
3. **已给文章链接**：若需定位账号且 `search` 返回 `-2041`，先运行 `python3 scripts/download_weread.py identify 'https://mp.weixin.qq.com/s/...' --expect-account '准确名称'`；该步骤只读公开原文页，验证署名与 `biz` 后输出候选 `MP_WXS_<数字>`，不请求微信读书；待冷却结束再单次试 `list ID 0 3`，列表再被验证则停。2026-10-29「孔小黑进城」`/mp/chapters` 已再次返回 `-2041`，不能只靠跳过搜索解决最近三篇发现。单篇正文运行 `python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/...' ./wechat_downloads`；怀疑缓存时在子命令前加 `--refresh`。核对退出码、文件大小与原文链接；普通文章检查开头／中段／结尾，图片分享检查全部本地图片引用及首／中／末图片能解码。仅有作者、摘要或“阅读原文／不喜欢”且没有原图时不算内容。
4. **仅给公众号名称**：先 `search '名称'`，从 `bookInfo.bookId` 确认真实 `MP_WXS_<数字>`（不能使用旧 `fakeid`）；再 `list ID 0 5`、`download ID 1 ./wechat_downloads`，确认真实落盘后才逐步增大数量。默认 200、最多 1,000 篇；这是请求上限，不是历史覆盖承诺。
5. 若用户已在 `weread.qq.com` 网页登录且愿意尝试实验通道，可指引其在本机执行 `python3 scripts/download_weread.py web-cookie`，从浏览器开发者工具复制该站点 Cookie 值到隐藏终端提示；程序仅向固定微信读书 Web 正文接口请求，失败仍按相同原文 URL 尝试 RSS，不能承诺成功。2026-10-28 无 Web 会话时实测 `errCode=-2010`；本轮最新三篇已由正常正文＋图片分享路线全部归档，不需要假称两篇图片分享有纯文本全文。
6. 阅读 `.md` 内容，核对 `failures.json`、实际文件数量与错误。若上游未识别公众号名称且用户已明确给出准确名称，可在 `url` 或 `download` 后添加 `--rss-account '名称'` 供自动兜底使用；RSS 必须匹配同一篇文章，不能替换成“相似”文章。以最终退出码和实际 `.md`／本地图片为准：空列表、0 文件、仅摘要且无图、图片缺失或最终失败不可报成功；上游的 `SOURCE_CONTENT_INSUFFICIENT` 也可能由结构化正文或图片画廊备用路线恢复，不能只看中间错误。`-2041` 不能简单当作限流：另一个客户端漏传 `synckey` 曾返回同码，但本项目首列表请求已带 `synckey=0`，搜索接口亦报错；不要盲改参数或高频重登。可请用户本人在微信读书官方网页版打开公众号文章并完成若出现的验证码，或在 App 尝试「隐私→重新授权公众号」；清理登录设备会登出其他设备且未经本项目验证，仅可作为用户自选最后手段。`-2041` 后运行 `pace-status`：持久熔断至少 30 分钟，到期仅单次低频探测，再失败加倍冷却（最高 24 小时），不得短时反复搜索；已知原文链接在本地熔断时可尝试独立公开原文页与精确 RSS，但不能将中间摘要当成功。不保证手机 App 一定有验证入口。只有用户在官方客户端完成要求的验证后，才运行 `pace-reset --verified` 提前解除。
7. 微信读书不可用或文章不可读时，若用户给出**公众号名称**，可 `download_rss.py search '名称'`；命中后使用返回的 Feed URL `list URL`、`download URL 1 ./wechat_downloads`，只将真实 `content:encoded` 文件称为已下载。第三方源超时、目录缺号、正文不足时如实报告，不生成伪文件。
8. 用户提出定时任务时，只有在其指定目标和周期后才配置 Agent 外部调度；先实测目标号最近若干篇。持久化输出目录，报告新增、跳过、失败和退出码；失败不可报“无新文”。当前「匿名测试公众号」最新三篇已归档 1 篇正文＋2 篇原图画廊，共 15 张本地图片；再次批量运行应当跳过 3 篇且失败为 0。任何图片引用缺失、文件未落盘或命令非零退出都不可宣称定时下载成功；文本检索图片需另做 OCR。
9. 不自动关注公众号，不调用订阅写接口，除非用户明确授权；输出图片链接可能仍是远程地址。真实下载产物保留，临时二维码、抓取中间文件与失败测试目录在验收后清理；用户家目录中的登录凭证不得清除。

## 常用命令

```bash
bash scripts/install_weread_cli.sh
python3 scripts/download_weread.py login
python3 scripts/download_weread.py status
python3 scripts/download_weread.py pace-status
python3 scripts/download_weread.py identify 'https://mp.weixin.qq.com/s/TG5KkixnncIrunVZF2ROKQ' --expect-account '孔小黑进城'
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
