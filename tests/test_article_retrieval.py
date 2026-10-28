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
        self.assertEqual(delays, [2, 4, 8])
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
