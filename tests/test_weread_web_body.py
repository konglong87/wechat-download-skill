import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from weread_client import WeReadError
from weread_web_body import WeReadWebBody, extract_body, store_cookie

REVIEW_ID = "MP_WXS_1234567890_QZDG~IZuUcnq7lWVlMo3eA"


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, n): return self.body[:n]


class WebBodyTests(unittest.TestCase):
    def _client(self, body):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        secret = Path(temp.name) / "session.cookie"
        secret.write_text("session=example; testing=1", encoding="ascii")
        secret.chmod(0o600)
        opener = Mock()
        opener.open.return_value = FakeResponse(body.encode("utf-8"))
        return WeReadWebBody(secret, opener=opener), opener

    def test_fragment_produces_readable_body_and_exact_review_id(self):
        html = "<section><p>有实际正文的一段文本。</p></section>" * 15
        client, opener = self._client(html)
        result = client.read(REVIEW_ID, title="测试标题", account_name="目标号")
        self.assertIn("实际正文", result["markdown"])
        self.assertEqual(result["title"], "测试标题")
        self.assertIn("微信读书网页", result["contentSource"])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url.split("?")[0], "https://weread.qq.com/web/mp/content")
        self.assertIn("reviewId=MP_WXS_1234567890_", request.full_url)
        self.assertEqual(request.get_header("Cookie"), "session=example; testing=1")

    def test_full_article_selects_js_content_and_ignores_shell(self):
        html = "<html><head><title>菜单</title></head><body>" + (
            "<div>" + ("导航菜单" * 100) + "</div><div id='js_content'><img src='https://example.com/photo.jpg'><p>真实文章段落。</p>" * 20 + "</div><div>页脚菜单</div>"
        ) + "</body></html>"
        text = extract_body(html)
        self.assertIn("真实文章段落", text)
        self.assertNotIn("导航菜单", text)
        self.assertNotIn("页脚菜单", text)

    def test_content_noencode_on_normal_article_page(self):
        content = "<p>正常文章正文段落。</p>" * 20
        html = "<html><body><script>var content_noencode = " + json.dumps(content) + ";</script></body></html>"
        self.assertIn("正常文章正文", extract_body(html))

    def test_content_noencode_used_when_js_content_empty(self):
        content = "<section><p>真正的文章正文段落。</p></section>" * 20
        html = "<html><body><div id='js_content'></div><script>var content_noencode = " + json.dumps(content) + ";</script></body></html>"
        self.assertIn("真正的文章", extract_body(html))

    def test_login_response_is_not_a_body(self):
        client, _ = self._client(json.dumps({"errCode": -2010, "errMsg": "用户不存在"}))
        with self.assertRaises(WeReadError) as raised:
            client.read(REVIEW_ID)
        self.assertEqual(raised.exception.code, "WEB_LOGIN_REQUIRED")

    def test_verification_and_navigation_shell_fail_closed(self):
        for html in (
            "<html><body><div>扫码登录微信读书</div></body></html>",
            "<html><body><div>验证</div><a href='/mp/wappoc_appmsgcaptcha'>继续</a></body></html>",
            "<html><body><div>" + "菜单信息" * 100 + "</div></body></html>",
            "<div><p>标题</p></div>",
        ):
            with self.subTest(html=html[:35]), self.assertRaises(WeReadError):
                extract_body(html)

    def test_rejects_invalid_review_ids_before_network(self):
        client, opener = self._client("<p>正文</p>" * 100)
        for review in ("https://evil.example/x", "MP_WXS_123_../hack", "", "MP_WXS_123"):
            with self.subTest(review=review), self.assertRaises(WeReadError):
                client.read(review)
        opener.open.assert_not_called()

    def test_cookie_prompt_saves_private_without_echoing_secret(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "secrets" / "web.cookie"
            returned = store_cookie(path, prompt=lambda _: "session=example")
            self.assertEqual(returned, path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_text(), "session=example")
            with self.assertRaises(WeReadError):
                store_cookie(path, prompt=lambda _: "invalid\nvalue=1")
            self.assertEqual(path.read_text(), "session=example")

    def test_cookie_must_be_private_file(self):
        client, opener = self._client("<p>正文</p>" * 100)
        client.cookie_file.chmod(0o644)
        with self.assertRaises(WeReadError) as raised:
            client.read(REVIEW_ID)
        self.assertEqual(raised.exception.code, "WEB_COOKIE_PERMISSIONS")
        opener.open.assert_not_called()

    def test_redirect_never_leaks_cookie_to_new_host(self):
        from weread_web_body import NoRedirect
        with self.assertRaises(WeReadError):
            NoRedirect().redirect_request(Mock(), None, 302, "Found", {}, "https://elsewhere.example/")


if __name__ == "__main__":
    unittest.main()
