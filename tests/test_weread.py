import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from download_weread import _save_article, collect_articles, download_account, download_url
from download_rss import RSSError
from weread_client import WeReadClient, WeReadError, article_url

ACCOUNT = "MP_WXS_1234567890"
ARTICLE_URL = "https://mp.weixin.qq.com/s/example"


class FakeClient:
    def __init__(self, pages=None, error=None):
        self.pages = pages or {}
        self.error = error
        self.calls = []

    def articles(self, account_id, count, offset):
        self.calls.append((account_id, count, offset))
        if self.error:
            raise WeReadError(self.error)
        return self.pages.get(offset, {"articles": []})

    def resolve_url(self, entry):
        return entry.get("mpInfo", {}).get("doc_url")

    def read(self, url):
        if self.error:
            raise WeReadError(self.error)
        return {"status": "readable", "title": "示例标题", "accountName": "示例公众号", "markdown": "正文内容" * 60}


class WeReadTests(unittest.TestCase):
    def test_direct_url_deduplicates_changed_review_id_and_keeps_gallery_links(self):
        class GalleryClient:
            def __init__(self): self.calls = 0
            def read(self, url):
                self.calls += 1
                review_id = "upstream-" + str(self.calls)
                source_digest = hashlib.sha256(review_id.encode()).hexdigest()[:12]
                return {"reviewId": review_id, "title": "图片文章", "markdown":
                        "## 原文图片（1 张，已下载到本地）\n\n![原图](" + source_digest + "_images/01.png)",
                        "assets": [{"filename": "01.png", "data": b"\x89PNG\r\n\x1a\n" + b"0" * 600}],
                        "contentSource": "微信公众号图片分享"}
        client = GalleryClient()
        url_digest = hashlib.sha256(ARTICLE_URL.encode()).hexdigest()[:12]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(download_url(client, ARTICLE_URL, directory), 0)
            self.assertEqual(download_url(client, ARTICLE_URL, directory), 0)
            files = list(Path(directory).glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].name.startswith(url_digest + "_"))
            self.assertIn(url_digest + "_images/01.png", files[0].read_text())
            self.assertTrue((Path(directory) / (url_digest + "_images/01.png")).is_file())

    def test_legacy_review_id_archive_is_reused_by_exact_url(self):
        class ChangedReviewClient(FakeClient):
            def read(self, url):
                return {**super().read(url), "reviewId": "different-review-id"}
        with tempfile.TemporaryDirectory() as directory:
            old = {"reviewId": "old-review-id", "title": "示例标题", "markdown": "正文内容" * 60}
            path, saved = _save_article(Path(directory), "old-review-id", "示例标题", ARTICLE_URL, {}, old)
            self.assertTrue(saved)
            self.assertEqual(download_url(ChangedReviewClient(), ARTICLE_URL, directory), 0)
            self.assertEqual(list(Path(directory).glob("*.md")), [path])

    def test_article_url_allowlist(self):
        self.assertEqual(article_url(ARTICLE_URL), ARTICLE_URL)
        for value in ("http://mp.weixin.qq.com/s/x", "https://evil.example/s/x", "file:///etc/passwd", "https://mp.weixin.qq.com:bad/s/x"):
            self.assertIsNone(article_url(value))

    def test_cli_arguments_and_json(self):
        runner = Mock(return_value=Mock(returncode=0, stdout=json.dumps({"articles": []}), stderr=""))
        client = WeReadClient(executable="/some/cli", account="default", runner=runner)
        self.assertEqual(client.articles(ACCOUNT, 2)["articles"], [])
        self.assertEqual(runner.call_args.args[0], ["/some/cli", "--account", "default", "--json", "public-accounts", "articles", ACCOUNT, "--count", "2"])
        client.articles(ACCOUNT, 2, offset=20)
        self.assertEqual(runner.call_args.args[0][-2:], ["--offset", "20"])

    def test_cli_fails_closed(self):
        runner = Mock(return_value=Mock(returncode=1, stdout="", stderr='{"error":"freq control"}'))
        client = WeReadClient(executable="/some/cli", runner=runner)
        with self.assertRaisesRegex(WeReadError, "freq control"):
            client.articles(ACCOUNT)

    def test_structured_cli_error_keeps_code_and_account_without_raw_article(self):
        payload = {"error": "article source content was insufficient", "code": "SOURCE_CONTENT_INSUFFICIENT",
                   "article": {"accountName": "示例公众号", "sourceUrl": "private-token"}}
        runner = Mock(return_value=Mock(returncode=1, stdout="", stderr=json.dumps(payload)))
        client = WeReadClient(executable="/some/cli", runner=runner)
        with self.assertRaises(WeReadError) as caught:
            client.read(ARTICLE_URL, refresh=True)
        self.assertEqual(caught.exception.code, "SOURCE_CONTENT_INSUFFICIENT")
        self.assertEqual(caught.exception.account_name, "示例公众号")
        self.assertNotIn("private-token", str(caught.exception))
        self.assertIn("--refresh", runner.call_args.args[0])

    def test_unreadable_response_preserves_account_for_rss_fallback(self):
        runner = Mock(return_value=Mock(returncode=0, stdout=json.dumps({
            "status": "unavailable", "accountName": "示例公众号"}), stderr=""))
        client = WeReadClient(executable="/some/cli", runner=runner)
        with self.assertRaises(WeReadError) as caught:
            client.read(ARTICLE_URL)
        self.assertEqual(caught.exception.account_name, "示例公众号")
        self.assertEqual(caught.exception.code, "SOURCE_CONTENT_UNAVAILABLE")

    def test_chrome_only_preview_is_not_saved(self):
        preview = {
            "status": "readable", "completeness": "unverified",
            "title": "示例标题", "accountName": "小众软件",
            "markdown": "原创 青小蛙 小众软件\n\n阅读原文 不喜欢",
            "contentHtml": '<div id="js_article"><p>阅读原文 不喜欢</p></div>',
        }
        runner = Mock(return_value=Mock(returncode=0, stdout=json.dumps(preview), stderr=""))
        client = WeReadClient(executable="/some/cli", runner=runner)
        fallback = Mock()
        fallback.fetch.side_effect = RSSError("not indexed")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(WeReadError, "RSS fallback unavailable"):
                download_url(client, ARTICLE_URL, d, rss_fallback=fallback, sleep=lambda _: None)
            self.assertEqual(list(Path(d).glob("*.md")), [])

    def test_long_unverified_article_is_saved(self):
        article = {
            "status": "readable", "completeness": "unverified",
            "title": "示例标题", "accountName": "示例公众号",
            "markdown": "有意义的正文内容。" * 100,
        }
        runner = Mock(return_value=Mock(returncode=0, stdout=json.dumps(article), stderr=""))
        client = WeReadClient(executable="/some/cli", runner=runner)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_url(client, ARTICLE_URL, d), 0)
            saved = list(Path(d).glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertIn("有意义的正文内容", saved[0].read_text(encoding="utf-8"))

    def test_paginated_articles(self):
        first = [{"reviewId": "r{}".format(i), "title": str(i)} for i in range(20)]
        client = FakeClient({None: {"articles": first, "nextOffset": 20}, 20: {"articles": [{"reviewId": "r20", "title": "20"}]}})
        items = collect_articles(client, ACCOUNT, 21, sleep=lambda _: None)
        self.assertEqual(len(items), 21)
        self.assertEqual(client.calls, [(ACCOUNT, 20, None), (ACCOUNT, 1, 20)])

    def test_batch_download_and_readback(self):
        client = FakeClient({None: {"articles": [{"reviewId": "r1", "title": "示例标题", "mpInfo": {"doc_url": ARTICLE_URL}}]}})
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "articles"
            self.assertEqual(download_account(client, ACCOUNT, 1, out, sleep=lambda _: None), 0)
            files = list(out.glob("*.md"))
            self.assertEqual(len(files), 1)
            self.assertIn("正文内容", files[0].read_text(encoding="utf-8"))
            self.assertIn(ARTICLE_URL, files[0].read_text(encoding="utf-8"))
            self.assertEqual(download_account(client, ACCOUNT, 1, out, sleep=lambda _: None), 0)
            self.assertEqual(len(list(out.glob("*.md"))), 1)

    def test_list_error_does_not_claim_success_or_create_output(self):
        client = FakeClient(error="freq control")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "output"
            with self.assertRaisesRegex(WeReadError, "freq control"):
                download_account(client, ACCOUNT, 1, out, sleep=lambda _: None)
            self.assertFalse(out.exists())

    def test_read_error_returns_nonzero_and_failure_file(self):
        class FailingReader(FakeClient):
            def read(self, url):
                raise WeReadError("WeRead upstream unavailable")
        client = FailingReader({None: {"articles": [{"reviewId": "r1", "mpInfo": {"doc_url": ARTICLE_URL}}]}})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_account(client, ACCOUNT, 1, Path(d), sleep=lambda _: None), 1)
            self.assertEqual(len(json.loads((Path(d) / "failures.json").read_text())), 1)

    def test_batch_failure_uses_nested_mp_title(self):
        class FailingReader(FakeClient):
            def read(self, url):
                raise WeReadError("article source content was insufficient")
        entry = {"reviewId": "r1", "mpInfo": {"title": "最新文章", "doc_url": ARTICLE_URL}}
        client = FailingReader({None: {"articles": [entry]}})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_account(client, ACCOUNT, 1, d, sleep=lambda _: None), 1)
            failures = json.loads((Path(d) / "failures.json").read_text(encoding="utf-8"))
            self.assertEqual(failures[0]["title"], "最新文章")

    def test_successful_retry_removes_stale_failure_report(self):
        entry = {"reviewId": "r1", "mpInfo": {"title": "最新文章", "doc_url": ARTICLE_URL}}
        client = FakeClient({None: {"articles": [entry]}})
        with tempfile.TemporaryDirectory() as d:
            failure_path = Path(d) / "failures.json"
            failure_path.write_text('[{"error":"old failure"}]', encoding="utf-8")
            self.assertEqual(download_account(client, ACCOUNT, 1, d, sleep=lambda _: None), 0)
            self.assertFalse(failure_path.exists())
            self.assertEqual(len(list(Path(d).glob("*.md"))), 1)

    def test_second_page_failure_keeps_first_page_files(self):
        class FailingSecondPage(FakeClient):
            def articles(self, account_id, count, offset):
                if offset is not None:
                    raise WeReadError("freq control")
                return super().articles(account_id, count, offset)
        entries = [
            {"reviewId": "r{}".format(i), "title": "item {}".format(i), "mpInfo": {"doc_url": ARTICLE_URL + str(i)}}
            for i in range(20)
        ]
        client = FailingSecondPage({None: {"articles": entries, "nextOffset": 20}})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_account(client, ACCOUNT, 21, d, sleep=lambda _: None), 1)
            self.assertEqual(len(list(Path(d).glob("*.md"))), 20)
            self.assertIn("Article list", (Path(d) / "failures.json").read_text())

    def test_empty_list_is_an_error(self):
        with self.assertRaisesRegex(WeReadError, "No articles returned"):
            collect_articles(FakeClient(), ACCOUNT, 1, sleep=lambda _: None)

    def test_direct_url_recovers_exact_rss_article_after_three_retries(self):
        class FailingReader(FakeClient):
            def __init__(self): super().__init__(); self.read_calls = []
            def read(self, url, refresh=None):
                self.read_calls.append(refresh)
                raise WeReadError("content insufficient", code="SOURCE_CONTENT_INSUFFICIENT", account_name="示例公众号")
        client = FailingReader()
        fallback = Mock()
        fallback.fetch.return_value = {"title": "RSS文章", "accountName": "示例公众号", "publishedAt": "today",
                                      "markdown": "从RSS读取的正文。" * 80, "contentSource": "公开 RSS（第三方）"}
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_url(client, ARTICLE_URL, d, rss_fallback=fallback, sleep=lambda _: None), 0)
            saved = list(Path(d).glob("*.md"))
            self.assertEqual(len(saved), 1)
            self.assertIn("内容渠道：公开 RSS", saved[0].read_text(encoding="utf-8"))
            self.assertIn("从RSS读取的正文", saved[0].read_text(encoding="utf-8"))
        self.assertEqual(client.read_calls, [None, True, True, True])
        fallback.fetch.assert_called_once_with(ARTICLE_URL, "示例公众号")

    def test_batch_uses_same_rss_fallback_after_three_retries(self):
        class FailingReader(FakeClient):
            def read(self, url, refresh=None):
                raise WeReadError("content insufficient", code="SOURCE_CONTENT_INSUFFICIENT", account_name="示例公众号")
        entry = {"reviewId": "r1", "mpInfo": {"title": "RSS文章", "doc_url": ARTICLE_URL}}
        client = FailingReader({None: {"articles": [entry]}})
        fallback = Mock()
        fallback.fetch.return_value = {"title": "RSS文章", "accountName": "示例公众号",
                                      "markdown": "从RSS读取的正文。" * 80, "contentSource": "公开 RSS（第三方）"}
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_account(client, ACCOUNT, 1, d, rss_fallback=fallback, sleep=lambda _: None), 0)
            self.assertEqual(len(list(Path(d).glob("*.md"))), 1)
            self.assertFalse((Path(d) / "failures.json").exists())

    def test_direct_review_id_file_is_reused_by_batch(self):
        class Client(FakeClient):
            def read(self, url):
                result = super().read(url)
                result["reviewId"] = "r1"
                return result
        entry = {"reviewId": "r1", "mpInfo": {"title": "示例标题", "doc_url": ARTICLE_URL}}
        client = Client({None: {"articles": [entry]}})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_url(client, ARTICLE_URL, d), 0)
            self.assertEqual(download_account(client, ACCOUNT, 1, d, sleep=lambda _: None), 0)
            self.assertEqual(len(list(Path(d).glob("*.md"))), 1)

    def test_known_url_download(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(download_url(FakeClient(), ARTICLE_URL, d), 0)
            self.assertEqual(len(list(Path(d).glob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
