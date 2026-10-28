from pathlib import Path
from html import escape
import sys
import re
import io
import urllib.error
from unittest.mock import Mock
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import download_rss as rss

FEED = "https://wechat2rss.xlab.app/feed/" + "a" * 40 + ".xml"
LINK = "https://mp.weixin.qq.com/s?__biz=AAA&mid=1&idx=1&sn=valid"
CATALOG = ('<html><a href="{}">测试公众号</a><a href="https://evil.example/feed/x.xml">ignored</a></html>'.format(FEED)).encode()
XML = ('''<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0"><channel>
<title>测试公众号</title><item><title>真实标题</title><link>{}</link>
<pubDate>Wed, 28 Oct 2026 10:00:00 +0800</pubDate>
<content:encoded><![CDATA[<p>正文开始，这是一段具有实际长度的内容，供离线下载单元测试使用。</p>
<p>第二段内容说明完整正文来自 RSS 条目，而不是只保存标题或摘要。确认结果可以读回验证，文件保持纯文本且不会执行 HTML。</p>
<script>SHOULD_NOT_APPEAR</script><img data-src="https://mmbiz.qpic.cn/test.png" />]]></content:encoded>
</item></channel></rss>'''.format(escape(LINK))).encode()


class RSSTests(unittest.TestCase):
    def test_timeout_retries_once_without_bypassing_refusal(self):
        opener = Mock()
        opener.open.side_effect = [TimeoutError("temporary"), io.BytesIO(b"ok")]
        with patch.object(rss.urllib.request, "build_opener", return_value=opener), patch.object(rss.time, "sleep") as sleep:
            self.assertEqual(rss._fetch(FEED), b"ok")
            self.assertEqual(opener.open.call_count, 2)
            sleep.assert_called_once_with(2)
        opener.open.reset_mock()
        opener.open.side_effect = urllib.error.HTTPError(FEED, 403, "blocked", {}, None)
        with patch.object(rss.urllib.request, "build_opener", return_value=opener), patch.object(rss.time, "sleep") as sleep:
            with self.assertRaisesRegex(rss.RSSError, "HTTP 403"):
                rss._fetch(FEED)
            self.assertEqual(opener.open.call_count, 1)
            sleep.assert_not_called()

    def test_feed_url_allowlist(self):
        self.assertEqual(rss.validated_feed_url(FEED), FEED)
        for url in ("http://wechat2rss.xlab.app/feed/" + "a"*40 + ".xml", "https://evil.example/feed/x.xml", FEED + "?x=1", "file:///etc/passwd"):
            self.assertIsNone(rss.validated_feed_url(url))

    def test_catalog_search_and_exact_resolution(self):
        with patch.object(rss, "_fetch", return_value=CATALOG):
            self.assertEqual(rss.search_accounts("测试")[0]["feed"], FEED)
            self.assertEqual(rss.resolve_feed("测试公众号"), FEED)

    def test_feed_content_download_and_readback(self):
        with patch.object(rss, "_fetch", return_value=XML):
            name, items = rss.read_feed(FEED)
            self.assertEqual(name, "测试公众号")
            self.assertEqual(len(items), 1)
            with tempfile.TemporaryDirectory() as temp:
                self.assertEqual(rss.download_feed(FEED, 1, temp), 0)
                files = list(Path(temp).glob("*.txt"))
                self.assertEqual(len(files), 1)
                text = files[0].read_text(encoding="utf-8")
                self.assertIn("正文开始", text)
                self.assertIn(LINK, text)
                self.assertIn("[图片] https://mmbiz.qpic.cn/test.png", text)
                self.assertNotIn("SHOULD_NOT_APPEAR", text)
                self.assertEqual(rss.download_feed(FEED, 1, temp), 0)
                self.assertEqual(len(list(Path(temp).glob("*.txt"))), 1)

    def test_incomplete_feed_returns_nonzero(self):
        with patch.object(rss, "_fetch", return_value=XML):
            with tempfile.TemporaryDirectory() as temp:
                self.assertEqual(rss.download_feed(FEED, 2, temp), 1)

    def test_missing_body_fails_instead_of_using_summary(self):
        xml = re.sub(rb"<!\[CDATA\[.*?\]\]>", b"<![CDATA[<p>short</p>]]>", XML, flags=re.S)
        with patch.object(rss, "_fetch", return_value=xml):
            with tempfile.TemporaryDirectory() as temp:
                self.assertEqual(rss.download_feed(FEED, 1, temp), 1)
                self.assertEqual(len(list(Path(temp).glob("*.txt"))), 0)
                self.assertTrue((Path(temp) / "failures.json").exists())


if __name__ == "__main__":
    unittest.main()
