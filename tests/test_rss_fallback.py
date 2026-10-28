import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from download_rss import RSSError
from rss_fallback import RSSFallback, article_identity

ARTICLE = "https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=123&idx=1&sn=456&chksm=tracking"
FEED_LINK = "https://mp.weixin.qq.com/s?sn=456&idx=1&mid=123&__biz=abc%3D%3D&scene=88"


class RSSFallbackTests(unittest.TestCase):
    def test_matches_exact_article_ignoring_tracking_parameters(self):
        calls = []
        def resolve(name):
            calls.append(name)
            return "https://wechat2rss.xlab.app/feed/" + "a" * 40 + ".xml"
        def read(url):
            return "示例公众号", [{"url": FEED_LINK, "title": "真实标题", "published": "today", "html": "<p>可靠的正文。</p>" * 20}]
        fallback = RSSFallback(resolve=resolve, read=read)
        result = fallback.fetch(ARTICLE, "示例公众号")
        self.assertIn("可靠的正文", result["markdown"])
        self.assertEqual(result["title"], "真实标题")
        self.assertIn("第三方", result["contentSource"])
        fallback.fetch(ARTICLE, "示例公众号")
        self.assertEqual(calls, ["示例公众号"])

    def test_refuses_similar_title_with_different_article_id(self):
        wrong = FEED_LINK.replace("sn=456", "sn=other")
        fallback = RSSFallback(resolve=lambda _: "https://example.invalid/", read=lambda _: (
            "示例公众号", [{"url": wrong, "title": "真实标题", "published": "", "html": "<p>正文</p>" * 50}]))
        with self.assertRaisesRegex(RSSError, "no item matching"):
            fallback.fetch(ARTICLE, "示例公众号")

    def test_rejects_missing_body_and_incomplete_identifiers(self):
        fallback = RSSFallback(resolve=lambda _: "https://example.invalid/", read=lambda _: (
            "示例公众号", [{"url": FEED_LINK, "title": "真实标题", "published": "", "html": "<p>摘要</p>"}]))
        with self.assertRaisesRegex(RSSError, "too short"):
            fallback.fetch(ARTICLE, "示例公众号")
        self.assertIsNone(article_identity("https://mp.weixin.qq.com/s?mid=123"))
        self.assertIsNone(article_identity("https://evil.example/s/article"))

    def test_failed_catalog_lookup_is_cached_per_batch(self):
        calls = []
        def resolve(name):
            calls.append(name)
            raise RSSError("not indexed")
        fallback = RSSFallback(resolve=resolve)
        for _ in range(2):
            with self.assertRaisesRegex(RSSError, "not indexed"):
                fallback.fetch(ARTICLE, "示例公众号")
        self.assertEqual(calls, ["示例公众号"])


if __name__ == "__main__":
    unittest.main()
