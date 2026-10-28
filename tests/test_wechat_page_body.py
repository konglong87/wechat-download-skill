from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from wechat_page_body import WeChatPageBody, NoRedirect, extract_visible_body
from weread_client import WeReadError

ARTICLE_URL = "https://mp.weixin.qq.com/s?__biz=abc&mid=123&idx=1&sn=abcdef"
TITLE = "测试文章标题"


class FakeResponse:
    url = ARTICLE_URL

    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, limit): return self.body[:limit]


class PublicPageTests(unittest.TestCase):
    def test_real_body_is_not_rejected_for_challenge_words_in_article_text(self):
        page = "<html><head><title>{}</title></head><body><div id='js_content'>".format(TITLE)
        page += "<section><p>执行敏感操作时需要验证身份；这是业务需求，不是验证页面。</p></section>" * 30
        page += "</div><script>var unrelated = '导航'</script></body></html>"
        body = extract_visible_body(page, title=TITLE, preview="一段短摘要")
        self.assertGreater(len(body), 500)
        self.assertIn("需要验证", body)
        self.assertNotIn("导航", body)

    def test_full_js_content_noencode_is_decoded_without_execution(self):
        encoded = "\\x3cp\\x3e" + "正文内容" * 250 + "\\x3c/p\\x3e"
        page = "<html><head><title>{}</title></head><body><script>window.data = {{content_noencode: '{}'}};</script></body></html>".format(TITLE, encoded)
        body = extract_visible_body(page, title=TITLE, preview="短摘要")
        self.assertGreater(len(body), 500)
        self.assertNotIn("\\x3c", body)

    def test_preview_only_page_is_rejected_even_if_js_has_many_words(self):
        page = "<html><head><title>{}</title></head><body>".format(TITLE)
        page += "<script>var content_noencode = '摘要' + '内容' * 400</script></body></html>"
        with self.assertRaises(WeReadError) as exc:
            extract_visible_body(page, title=TITLE, preview="摘要")
        self.assertEqual(exc.exception.code, "SOURCE_CONTENT_INSUFFICIENT")

    def test_rejects_wrong_title_and_short_body(self):
        page = "<html><head><title>另一篇文章</title></head><body><div id='js_content'>"
        page += "<p>真正的正文</p>" * 90 + "</div></body></html>"
        with self.assertRaises(WeReadError) as exc:
            extract_visible_body(page, title=TITLE)
        self.assertEqual(exc.exception.code, "SOURCE_IDENTITY_MISMATCH")
        short = "<html><head><title>{}</title></head><body><div id='js_content'>摘要</div></body></html>".format(TITLE)
        with self.assertRaises(WeReadError):
            extract_visible_body(short, title=TITLE)

    def test_one_request_only_to_public_wechat_url(self):
        page = "<html><head><title>{}</title></head><body><div id='js_content'>".format(TITLE)
        page += "<p>内容文字需要验证，但此处在解释业务流程。</p>" * 40 + "</div></body></html>"
        opener = Mock()
        opener.open.return_value = FakeResponse(page.encode("utf-8"))
        client = WeChatPageBody(opener=opener)
        result = client.read(ARTICLE_URL, title=TITLE, account_name="匿名测试公众号",
                             review_id="MP_WXS_1234567890_abc")
        self.assertGreater(len(result["markdown"]), 500)
        self.assertEqual(result["reviewId"], "MP_WXS_1234567890_abc")
        self.assertIn("原文公开页", result["contentSource"])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, ARTICLE_URL)
        self.assertIn("WeRead/", request.get_header("User-agent"))
        with self.assertRaises(WeReadError):
            client.read("https://example.com/x")

    def test_redirect_to_verification_is_never_followed(self):
        with self.assertRaises(WeReadError) as exc:
            NoRedirect().redirect_request(Mock(), None, 302, "Found", {},
                "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?poc_token=secret")
        self.assertEqual(exc.exception.code, "SOURCE_WECHAT_CHALLENGE")


if __name__ == "__main__":
    unittest.main()
