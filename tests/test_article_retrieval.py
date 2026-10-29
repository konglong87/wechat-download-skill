import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from article_retrieval import read_article
from download_rss import RSSError
from weread_client import WeReadError

URL = "https://mp.weixin.qq.com/s/example"


class RetrievalTests(unittest.TestCase):
    def test_three_refresh_retries_then_weread_succeeds(self):
        class Client:
            def __init__(self): self.calls = []
            def read(self, url, refresh=None):
                self.calls.append((url, refresh))
                if len(self.calls) <= 3:
                    raise WeReadError("content insufficient", code="SOURCE_CONTENT_INSUFFICIENT", account_name="目标号")
                return {"markdown": "正文" * 100}
        client, fallback, delays = Client(), Mock(), []
        result = read_article(client, URL, fallback=fallback, sleep=delays.append)
        self.assertEqual(result["markdown"], "正文" * 100)
        self.assertEqual(client.calls, [(URL, None), (URL, True), (URL, True), (URL, True)])
        self.assertEqual(delays, [10, 30, 90])
        fallback.fetch.assert_not_called()

    def test_exhaustion_then_rss_uses_verified_account_name(self):
        class Client:
            def __init__(self): self.calls = 0
            def read(self, url, refresh=None):
                self.calls += 1
                raise WeReadError("content insufficient", code="SOURCE_CONTENT_INSUFFICIENT", account_name="目标号")
        client = Client()
        fallback = Mock()
        fallback.fetch.return_value = {"markdown": "RSS正文" * 100, "contentSource": "公开 RSS"}
        result = read_article(client, URL, fallback=fallback, sleep=lambda _: None)
        self.assertEqual(client.calls, 4)
        fallback.fetch.assert_called_once_with(URL, "目标号")
        self.assertEqual(result["contentSource"], "公开 RSS")

    def test_upstream_account_identity_overrides_manual_fallback_hint(self):
        client = Mock()
        client.read.side_effect = WeReadError("content insufficient", code="SOURCE_CONTENT_INSUFFICIENT", account_name="真实号")
        fallback = Mock()
        fallback.fetch.side_effect = RSSError("not indexed")
        with self.assertRaisesRegex(WeReadError, "not indexed"):
            read_article(client, URL, account_name="错误名称", fallback=fallback, sleep=lambda _: None)
        fallback.fetch.assert_called_once_with(URL, "真实号")

    def test_web_body_after_cli_failure_before_rss(self):
        class Client:
            def read(self, url, refresh=None):
                raise WeReadError("source blocked", code="SOURCE_CONTENT_INSUFFICIENT",
                                  review_id="MP_WXS_1234567890_abc", account_name="目标号",
                                  article_title="网页文章")
        web, rss = Mock(), Mock()
        web.read.return_value = {"markdown": "从网页获取正文" * 100, "contentSource": "微信读书网页"}
        result = read_article(Client(), URL, web_client=web, fallback=rss,
                              sleep=lambda _: self.fail("challenged: no retries"))
        self.assertIn("网页", result["contentSource"])
        web.read.assert_called_once_with("MP_WXS_1234567890_abc", title="网页文章",
                                         account_name="目标号", published_at=None)
        rss.fetch.assert_not_called()

    def test_web_login_failure_uses_exact_rss(self):
        class Client:
            def read(self, url, refresh=None):
                raise WeReadError("source blocked", code="SOURCE_CONTENT_INSUFFICIENT",
                                  review_id="MP_WXS_1234567890_abc", account_name="目标号")
        web, rss = Mock(), Mock()
        web.read.side_effect = WeReadError("web login expired", code="WEB_LOGIN_REQUIRED")
        rss.fetch.return_value = {"markdown": "RSS正文" * 100}
        result = read_article(Client(), URL, web_client=web, fallback=rss, sleep=lambda _: None)
        self.assertEqual(result["markdown"], "RSS正文" * 100)
        rss.fetch.assert_called_once_with(URL, "目标号")

    def test_source_body_rescues_upstream_false_block_without_rss(self):
        client, source, rss = Mock(), Mock(), Mock()
        client.read.side_effect = WeReadError("article source was blocked", code="SOURCE_CONTENT_INSUFFICIENT",
                                              review_id="MP_WXS_1234567890_abc", account_name="目标号",
                                              article_title="真实标题")
        source.read.return_value = {"markdown": "真实正文" * 200, "contentSource": "微信原文公开页"}
        result = read_article(client, URL, fallback=rss, source_client=source,
                              sleep=lambda _: self.fail("explicit blocked: no retry"))
        self.assertIn("真实正文", result["markdown"])
        source.read.assert_called_once_with(URL, title="真实标题", account_name="目标号",
                                            published_at=None, preview=None, review_id="MP_WXS_1234567890_abc")
        rss.fetch.assert_not_called()

    def test_source_preview_failure_continues_to_exact_rss(self):
        client, source, rss = Mock(), Mock(), Mock()
        client.read.side_effect = WeReadError("article source was blocked", code="SOURCE_CONTENT_INSUFFICIENT",
                                              account_name="目标号")
        source.read.side_effect = WeReadError("no full body", code="SOURCE_CONTENT_INSUFFICIENT")
        rss.fetch.return_value = {"markdown": "RSS正文" * 100}
        result = read_article(client, URL, fallback=rss, source_client=source, sleep=lambda _: None)
        self.assertIn("RSS正文", result["markdown"])
        rss.fetch.assert_called_once_with(URL, "目标号")

    def test_source_failure_then_web_success_before_rss(self):
        client, source, web, rss = Mock(), Mock(), Mock(), Mock()
        client.read.side_effect = WeReadError("article source was blocked", code="SOURCE_CONTENT_INSUFFICIENT",
                                              review_id="MP_WXS_1234567890_abc", account_name="目标号")
        source.read.side_effect = WeReadError("only preview", code="SOURCE_CONTENT_INSUFFICIENT")
        web.read.return_value = {"markdown": "网页登录正文" * 200}
        result = read_article(client, URL, source_client=source, web_client=web,
                              fallback=rss, sleep=lambda _: None)
        self.assertIn("网页登录正文", result["markdown"])
        source.read.assert_called_once()
        web.read.assert_called_once()
        rss.fetch.assert_not_called()

    def test_local_pacing_gate_uses_public_page_without_a_weread_retry(self):
        for code, message in (("HUMAN_VERIFICATION_REQUIRED", "Previous WeRead -2041; no request sent"),
                              ("PACING_COOLDOWN", "WeRead rate limit cooldown; no request sent")):
            with self.subTest(code=code):
                client, source, rss, web = Mock(), Mock(), Mock(), Mock()
                client.read.side_effect = WeReadError(message, code=code)
                source.read.return_value = {"markdown": "公开页真实正文" * 100,
                                            "contentSource": "微信原文公开页"}
                result = read_article(client, URL, account_name="目标号", fallback=rss,
                                      source_client=source, web_client=web,
                                      sleep=lambda _: self.fail("must not retry WeRead"))
                self.assertIn("真实正文", result["markdown"])
                client.read.assert_called_once_with(URL)
                source.read.assert_called_once()
                rss.fetch.assert_not_called()
                web.read.assert_not_called()

    def test_rate_limit_does_not_switch_to_web(self):
        client, web, rss, source = Mock(), Mock(), Mock(), Mock()
        client.read.side_effect = WeReadError("freq control -2041", review_id="MP_WXS_1234567890_abc")
        rss.fetch.side_effect = RSSError("not indexed")
        with self.assertRaises(WeReadError):
            read_article(client, URL, web_client=web, source_client=source, fallback=rss, sleep=lambda _: None)
        web.read.assert_not_called()
        source.read.assert_not_called()

    def test_rate_limit_or_challenge_does_not_retry(self):
        for error in (WeReadError("freq control -2041", status=499),
                      WeReadError("article source was blocked", code="SOURCE_CONTENT_INSUFFICIENT")):
            client = Mock()
            client.read.side_effect = error
            fallback = Mock()
            fallback.fetch.side_effect = RSSError("not indexed")
            with self.assertRaisesRegex(WeReadError, "RSS fallback unavailable"):
                read_article(client, URL, account_name="目标号", fallback=fallback, sleep=lambda _: self.fail("should not sleep"))
            self.assertEqual(client.read.call_count, 1)
            fallback.fetch.assert_called_once_with(URL, "目标号")


if __name__ == "__main__":
    unittest.main()
