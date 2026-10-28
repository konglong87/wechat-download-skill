---
name: wechat-download
description: Download, archive, or search WeChat official-account (公众号) articles, preferring a WeRead-backed workflow after the old MP history endpoint stopped working.
version: 1.1.0
---

# 微信公众号文章下载

## 架构与边界

新路线（真人扫码端到端验收前按实验性使用）：`download_weread.py → weread_client.py → weread-omni@0.1.2 (MIT) → 微信读书文章索引 / 微信文章正文`。
旧路由：`download_wechat.py → wechat-download-api → 微信公众平台后台`，保留用于兼容和已知文章链接，但**不要依赖**它批量获取公众号历史：2026-10-28 的实测中，`appmsgpublish` 返回 `ret=200013, freq control`。登录和搜索成功不等于文章列表成功。

微信读书使用非公开接口，数据是可用的索引快照，不保证全量历史。遵守访问权限、著作权和平台规则；遇到验证码、人工验证或限流，应请用户正常处理或停止，不得绕过。

## Agent 执行流程

1. 检查 Node.js >=22.13.0 与 Python >=3.9。优先寻找 `WEREAD_CLI`、PATH 中的 `weread-omni` 或默认安装路径；缺失则运行 `bash scripts/install_weread_cli.sh`。该脚本只安装固定版本，不需要公众号后台服务。
2. 运行 `python3 scripts/download_weread.py status`。如未登录，运行 `python3 scripts/download_weread.py login` 并将二维码呈现给用户，让**用户亲自**用微信读书账号扫码、确认和完成可能的二次验证。切勿读取、打印或提交 Cookie。原公众号后台扫码不能代替微信读书登录。
3. 已给文章链接时，直接运行 `python3 scripts/download_weread.py url 'https://mp.weixin.qq.com/s/...' ./wechat_downloads`，检查退出码及 `.md` 文件大小与正文。
4. 仅给公众号名称时，先 `python3 scripts/download_weread.py search '名称'`，核对返回的公众号身份，取得微信读书 `MP_WXS_<数字>`。不要把旧 `fakeid` 当微信读书 ID。
5. 运行 `python3 scripts/download_weread.py list MP_WXS_1234567890 0 10`；确认真实文章列表，再 `python3 scripts/download_weread.py download MP_WXS_1234567890 20 ./wechat_downloads`。默认下载数 200，最大 1,000；首先以小批量验收，再扩大数量。
6. 验证目标目录的 `.md` 文件确有正文，并检查 `failures.json`、退出码与实际数量。遇到频控/验证时停下来；不要把空列表或 0 文件当作成功。图片 URL 暂不本地化。

**关注公众号是写操作**：不要为了取列表自动调用 `weread-omni public-accounts subscribe`。若目标账号需要关注，先让用户确认并在微信读书 App 内操作或明确授权订阅。搜索或列表不要求默认关注；优先测试只读路线。

## 命令

```bash
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
- 真实验收必须核对微信读书扫码后的账号状态、公众号搜索、列表、导出文件读回；如果缺少真人扫码或遇上游验证，明确说出未验证的环节。
- 测试中间下载目录可清理；真实凭证在用户家目录，不要删除、输出或上传。旧服务启动时只能绑定到 `127.0.0.1`，不可把未鉴权的管理接口暴露给局域网。
