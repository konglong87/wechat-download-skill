import base64
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from wechat_account_identity import identify_html, identify_url
from weread_client import WeReadError

URL = "https://mp.weixin.qq.com/s/example"
BIZ = base64.b64encode(b"3227210349").decode()
HTML = '<h1 id="activity-name"> Agent正式进入下半场：做减法 </h1><strong id="js_name">孔小黑进城</strong><script>var biz = "' + BIZ + '";</script>'


class Response(io.BytesIO):
    def __init__(self, data, url=URL):
        super().__init__(data)
        self.url = url


class Opener:
    def __init__(self, data, url=URL):
        self.data, self.url, self.calls = data, url, 0

    def open(self, request, timeout=None):
        self.calls += 1
        return Response(self.data, self.url)


class IdentityTests(unittest.TestCase):
    def test_identify_name_title_and_numeric_id(self):
        opener = Opener(HTML.encode())
        result = identify_url(URL, expected_name="孔小黑进城", opener=opener)
        self.assertEqual(result, {"accountName": "孔小黑进城", "accountId": "MP_WXS_3227210349",
                                  "articleTitle": "Agent正式进入下半场：做减法"})
        self.assertEqual(opener.calls, 1)

    def test_nested_heading_and_article_text_cannot_override_script_identity(self):
        wrapped = ('<h1 id="activity-name">Agent<br><span>下半场</span></h1>'
                   '<strong id="js_name">孔小黑进城</strong>'
                   '<div>var biz = "' + base64.b64encode(b"1234567890").decode() + '"</div>'
                   '<script>var biz = "' + BIZ + '"</script>')
        result = identify_html(wrapped)
        self.assertEqual(result["articleTitle"], "Agent下半场")
        self.assertEqual(result["accountId"], "MP_WXS_3227210349")

    def test_mismatched_name_and_conflicting_ids_fail_closed(self):
        with self.assertRaises(WeReadError) as caught:
            identify_html(HTML, expected_name="另一个账号")
        self.assertEqual(caught.exception.code, "ACCOUNT_IDENTITY_MISMATCH")
        other = base64.b64encode(b"1234567890").decode()
        with self.assertRaises(WeReadError) as caught:
            identify_html(HTML + '<script>var __biz = "' + other + '"</script>')
        self.assertEqual(caught.exception.code, "ACCOUNT_BIZ_UNAVAILABLE")

    def test_rejects_unverified_page_and_redirect(self):
        for page in ('<div>请完成验证</div>', '<h1 id="activity-name">标题</h1><strong id="js_name">孔小黑进城</strong>'):
            with self.assertRaises(WeReadError):
                identify_html(page)
        with self.assertRaises(WeReadError) as caught:
            identify_url(URL, opener=Opener(HTML.encode(), 'https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha'))
        self.assertEqual(caught.exception.code, "SOURCE_WECHAT_CHALLENGE")
        with self.assertRaises(WeReadError):
            identify_url('https://evil.example/s/other', opener=Opener(HTML.encode()))


if __name__ == "__main__":
    unittest.main()
