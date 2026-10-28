import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import download_wechat


class LegacyFailureTests(unittest.TestCase):
    def test_failed_article_list_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(download_wechat, "_get", return_value={"success": False, "error": "freq control"}):
                with contextlib.redirect_stderr(io.StringIO()) as stream:
                    code = download_wechat.download_all("fakeid", 1, d)
            self.assertEqual(code, 1)
            self.assertIn("freq control", stream.getvalue())
            self.assertEqual(list(Path(d).glob("*.txt")), [])

    def test_empty_article_list_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(download_wechat, "_get", return_value={"success": True, "data": {"articles": [], "total": 0}}):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(download_wechat.download_all("fakeid", 1, d), 1)


if __name__ == "__main__":
    unittest.main()
