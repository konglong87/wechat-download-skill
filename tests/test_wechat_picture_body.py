import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from download_weread import _save_article, _existing_article
from wechat_picture_body import download_picture_post, picture_gallery
from weread_client import WeReadError

URL_1 = "https://mmbiz.qpic.cn/sz_mmbiz_png/first/0"
URL_2 = "https://mmbiz.qpic.cn/sz_mmbiz_png/second/0"
SOURCE = "https://mp.weixin.qq.com/s?__biz=abc&mid=123&idx=1&sn=abcdef"
REVIEW_ID = "MP_WXS_1234567890_abc"
TITLE = "测试图片分享"
PNG = b"\x89PNG\r\n\x1a\n" + b"A" * 900


def page_with_gallery(first=URL_1, second=URL_2):
    return (
        "<html><head><title>" + TITLE + "</title></head><body><script>"
        "var appmsg = {item_show_type: '8' * 1, picture_page_info_list: ["
        "{cdn_url: '" + first + "', width: '1080' * 1, height: '1440' * 1,"
        "watermark_info: {cdn_url: 'https://mmbiz.qpic.cn/watermark/0'},"
        "share_cover: {cdn_url: 'https://mmbiz.qpic.cn/cover/0'}},"
        "{cdn_url: '" + second + "', width: '1536' * 1, height: '1024' * 1}"
        "]};</script></body></html>"
    )


class ImageResponse:
    def __init__(self, url, body=PNG, mime="image/png"):
        self.url, self.body, self.headers = url, body, {"Content-Type": mime}
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def read(self, size): return self.body[:size]


class GalleryTests(unittest.TestCase):
    def test_top_level_gallery_ignores_nested_watermark_and_cover(self):
        records = picture_gallery(page_with_gallery())
        self.assertEqual(records, [(URL_1, 1080, 1440), (URL_2, 1536, 1024)])
        self.assertIsNone(picture_gallery(page_with_gallery().replace("item_show_type: '8'", "item_show_type: '0'")))

    def test_downloads_all_images_and_writes_relative_markdown(self):
        opener = Mock()
        opener.open.side_effect = [ImageResponse(URL_1), ImageResponse(URL_2)]
        result = download_picture_post(page_with_gallery(), opener=opener, user_agent="test",
            source_url=SOURCE, title=TITLE, account_name="目标号", published_at="2026-10-28",
            preview="图文简介", review_id=REVIEW_ID)
        digest = hashlib.sha256(REVIEW_ID.encode()).hexdigest()[:12]
        self.assertEqual(len(result["assets"]), 2)
        self.assertIn(digest + "_images/01.png", result["markdown"])
        self.assertIn("摘要＋全部原图", result["contentSource"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            path, saved = _save_article(output, REVIEW_ID, TITLE, SOURCE, {}, result)
            self.assertTrue(saved)
            self.assertEqual((output / (digest + "_images/01.png")).read_bytes(), PNG)
            self.assertEqual((output / (digest + "_images/02.png")).read_bytes(), PNG)
            self.assertEqual(_existing_article(output, digest), path)
            (output / (digest + "_images/02.png")).unlink()
            self.assertIsNone(_existing_article(output, digest), "Missing gallery assets cannot count as a saved article")

    def test_rejects_untrusted_hosts_duplicate_images_and_html_instead_of_image(self):
        with self.assertRaises(WeReadError):
            picture_gallery(page_with_gallery(first="https://example.com/evil"))
        with self.assertRaises(WeReadError):
            picture_gallery(page_with_gallery(first=URL_2))
        opener = Mock()
        opener.open.return_value = ImageResponse(URL_1, body=b"<html>not an image</html>" * 50, mime="text/html")
        with self.assertRaises(WeReadError) as caught:
            download_picture_post(page_with_gallery(), opener=opener, user_agent="test",
                source_url=SOURCE, title=TITLE, account_name="目标号", published_at=None,
                preview="short", review_id=REVIEW_ID)
        self.assertEqual(caught.exception.code, "PICTURE_INVALID_IMAGE")

    def test_save_failure_cleans_new_assets_and_preserves_existing_article(self):
        digest = hashlib.sha256(REVIEW_ID.encode()).hexdigest()[:12]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            existing = output / (digest + "_old.md")
            previous = "old content " * 15 + "![old](" + digest + "_images/99.png)"
            existing.write_text(previous, encoding="utf-8")
            result = {"markdown": "![原文第 1 张](" + digest + "_images/01.png)",
                      "assets": [{"filename": "01.png", "data": PNG},
                                 {"filename": "../unsafe.png", "data": PNG}]}
            with self.assertRaises(WeReadError):
                _save_article(output, REVIEW_ID, TITLE, SOURCE, {}, result)
            self.assertEqual(existing.read_text(encoding="utf-8"), previous)
            self.assertFalse((output / (digest + "_images/01.png")).exists())
            self.assertEqual(list(output.glob("*.part")), [])

    def test_no_partial_archive_when_second_image_fails(self):
        opener = Mock()
        opener.open.side_effect = [ImageResponse(URL_1), ImageResponse(URL_2, body=b"invalid" * 100, mime="text/html")]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(WeReadError):
                download_picture_post(page_with_gallery(), opener=opener, user_agent="test",
                    source_url=SOURCE, title=TITLE, account_name="目标号", published_at=None,
                    preview="short", review_id=REVIEW_ID)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
