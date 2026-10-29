import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from download_public import download_links, load_links
from wechat_page_body import PUBLIC_BROWSER_USER_AGENT, WeChatPageBody
from weread_client import WeReadError

ARTICLE_URL = "https://mp.weixin.qq.com/s/example-valid-id"
OTHER_URL = "https://mp.weixin.qq.com/s/another-valid-id"


class FakeResponse:
    def __init__(self, body):
        self.body = io.BytesIO(body)
        self.url = ARTICLE_URL

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size=-1):
        return self.body.read(size)


class PublicDownloadTests(unittest.TestCase):
    def test_manifest_deduplicates_and_rejects_other_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "urls.txt"
            manifest.write_text("# comments\n" + ARTICLE_URL + "\n\n" + ARTICLE_URL + "\n" + OTHER_URL + "\n")
            self.assertEqual(load_links(manifest), [ARTICLE_URL, OTHER_URL])
            manifest.write_text(ARTICLE_URL + "\nhttps://evil.example/s/x\n")
            with self.assertRaisesRegex(ValueError, "Line 2"):
                load_links(manifest)

    def test_verified_public_page_uses_browser_agent_and_actual_account(self):
        body = ('<meta property="og:title" content="文章标题">'
                '<a id="js_name">目标号</a><div id="js_content">' + '可见正文。' * 200 + '</div>').encode()
        opener = Mock()
        opener.open.return_value = FakeResponse(body)
        client = WeChatPageBody(opener=opener, user_agent=PUBLIC_BROWSER_USER_AGENT, verify_account=True)
        result = client.read(ARTICLE_URL, account_name="目标号")
        self.assertEqual(result["accountName"], "目标号")
        self.assertGreater(len(result["markdown"]), 500)
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(opener.open.call_args.args[0].get_header("User-agent"), PUBLIC_BROWSER_USER_AGENT)
        opener.open.return_value = FakeResponse(body)
        with self.assertRaises(WeReadError) as mismatch:
            client.read(ARTICLE_URL, account_name="另一个号")
        self.assertEqual(mismatch.exception.code, "ACCOUNT_IDENTITY_MISMATCH")
        opener.open.return_value = FakeResponse(b'<div id="js_content">' + b'x' * 1000 + b'</div>')
        with self.assertRaises(WeReadError) as missing:
            client.read(ARTICLE_URL)
        self.assertEqual(missing.exception.code, "ACCOUNT_IDENTITY_MISSING")

    def test_batch_preserves_successes_and_skips_existing_urls(self):
        source = Mock()
        source.read.return_value = {"title": "文章标题", "accountName": "目标号", "markdown": "正文。" * 250}
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(download_links([ARTICLE_URL], directory, account="目标号", source=source), 0)
            self.assertEqual(download_links([ARTICLE_URL], directory, account="目标号", source=source), 0)
            self.assertEqual(source.read.call_count, 1)
            self.assertEqual(download_links([ARTICLE_URL], directory, account="另一个号", source=source), 1)
            self.assertEqual(source.read.call_count, 1)
            self.assertEqual(len(list(Path(directory).glob("*.md"))), 1)
            source.read.side_effect = WeReadError("verification challenge", code="SOURCE_WECHAT_CHALLENGE")
            self.assertEqual(download_links([OTHER_URL, "https://mp.weixin.qq.com/s/third-id"], directory,
                                            source=source, sleep=lambda _: None), 1)
            self.assertEqual(source.read.call_count, 2)
            self.assertEqual(len(list(Path(directory).glob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
