"""Strict, bounded archive of public WeChat image-post galleries (item_show_type=8).

Image posts do not expose a normal #js_content article body. Their images are
content, not a preview of missing prose; archive every declared image locally
or fail without creating a false-success Markdown file.
"""

import hashlib
import re
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from weread_client import WeReadError

GALLERY_FIELD = "picture_page_info_list:"
PICTURE_TYPE = re.compile(r"item_show_type:\s*'8'\s*\*\s*1")
FIRST_IMAGE = re.compile(r"\{\s*cdn_url:\s*'([^']+)'\s*,\s*width:\s*'(\d+)'\s*\*\s*1,\s*height:\s*'(\d+)'", re.S)
MAX_PICTURES = 30
MAX_GALLERY_CHARACTERS = 1_000_000
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 64 * 1024 * 1024
MIN_IMAGE_BYTES = 500
IMAGE_TIMEOUT_SECONDS = 20
IMAGE_HOST = "mmbiz.qpic.cn"


def _objects_in_gallery(page, open_bracket):
    """Scan balanced JS objects without executing JS or confusing nested cover URLs."""
    bracket_depth, object_depth, start = 1, 0, None
    quote, escaped = None, False
    for index in range(open_bracket + 1, min(len(page), open_bracket + MAX_GALLERY_CHARACTERS)):
        char = page[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
            if bracket_depth == 0:
                return
        elif char == "{":
            if bracket_depth == 1 and object_depth == 0:
                start = index
            object_depth += 1
        elif char == "}":
            object_depth -= 1
            if object_depth == 0 and bracket_depth == 1 and start is not None:
                yield page[start:index + 1]
                start = None
    raise WeReadError("Image-post gallery is incomplete or too large", code="PICTURE_GALLERY_INVALID")


def picture_gallery(page):
    offset = page.find(GALLERY_FIELD)
    if offset < 0:
        return None
    preceding = page.rfind("item_show_type:", max(0, offset - 2500), offset)
    if preceding < 0 or not PICTURE_TYPE.match(page, preceding):
        return None
    bracket = page.find("[", offset + len(GALLERY_FIELD), offset + len(GALLERY_FIELD) + 40)
    if bracket < 0:
        raise WeReadError("Image-post gallery has no image list", code="PICTURE_GALLERY_INVALID")
    records = []
    for entry in _objects_in_gallery(page, bracket):
        if len(records) >= MAX_PICTURES:
            raise WeReadError("Image-post gallery exceeds the item limit", code="PICTURE_GALLERY_INVALID")
        match = FIRST_IMAGE.match(entry)
        if not match:
            raise WeReadError("Image-post gallery contains an unsupported image", code="PICTURE_GALLERY_INVALID")
        url, width, height = match.group(1), int(match.group(2)), int(match.group(3))
        try:
            parsed = urlsplit(url)
            trusted = (parsed.scheme == "https" and parsed.hostname == IMAGE_HOST and
                       not parsed.port and not parsed.username and not parsed.password and parsed.path.startswith("/"))
        except ValueError:
            trusted = False
        if not trusted:
            raise WeReadError("Image-post gallery contains an untrusted image URL", code="PICTURE_URL_INVALID")
        if not 100 <= width <= 10_000 or not 100 <= height <= 10_000:
            raise WeReadError("Image-post image dimensions are invalid", code="PICTURE_GALLERY_INVALID")
        records.append((url, width, height))
    if not records or len({url for url, _, _ in records}) != len(records):
        raise WeReadError("Image-post gallery is empty or duplicated", code="PICTURE_GALLERY_INVALID")
    return records


def _image_type(data, content_type):
    if not (content_type or "").lower().startswith("image/"):
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    return None


def download_picture_post(page, *, opener, user_agent, source_url, title, account_name,
                          published_at, preview, review_id):
    records = picture_gallery(page)
    if records is None:
        return None
    digest = hashlib.sha256((review_id or source_url).encode("utf-8")).hexdigest()[:12]
    assets, total_bytes = [], 0
    for number, (url, width, height) in enumerate(records, 1):
        request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "image/jpeg,image/png,image/webp,image/gif"})
        try:
            with opener.open(request, timeout=IMAGE_TIMEOUT_SECONDS) as response:
                if urlsplit(response.url).hostname != IMAGE_HOST:
                    raise WeReadError("Image-post CDN redirected away", code="PICTURE_URL_INVALID")
                content_type = response.headers.get("Content-Type", "")
                data = response.read(MAX_IMAGE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise WeReadError("Image-post image {} returned HTTP {}".format(number, exc.code), code="PICTURE_HTTP_ERROR") from exc
        except urllib.error.URLError as exc:
            raise WeReadError("Image-post image {} request failed".format(number), code="PICTURE_NETWORK_ERROR") from exc
        ext = _image_type(data, content_type)
        total_bytes += len(data)
        if ext is None or not MIN_IMAGE_BYTES <= len(data) <= MAX_IMAGE_BYTES or total_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise WeReadError("Image-post image {} is invalid or too large".format(number), code="PICTURE_INVALID_IMAGE")
        assets.append({"filename": "{:02d}.{}".format(number, ext), "data": data, "width": width, "height": height})
    intro = (preview or "").strip()
    text = (intro + "\n\n" if intro else "") + "## 原文图片（{} 张，已下载到本地）\n\n".format(len(assets))
    text += "\n\n".join("![原文第 {} 张（{}×{}）]({}_images/{})".format(
        index, asset["width"], asset["height"], digest, asset["filename"]
    ) for index, asset in enumerate(assets, 1))
    return {
        "reviewId": review_id, "title": title, "accountName": account_name, "publishedAt": published_at,
        "markdown": text, "assets": assets,
        "contentSource": "微信公众号图片分享（摘要＋全部原图；图片内文字尚未 OCR）",
    }
