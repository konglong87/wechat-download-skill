"""Shared, atomic Markdown archive for independently sourced article bodies."""

import hashlib
from pathlib import Path
import re

from weread_client import WeReadError

FILENAME_CHARACTERS = 55


def _slug(value):
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", value or "untitled")
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return (text or "untitled")[:FILENAME_CHARACTERS]


def _entry_title(entry, fallback):
    mp_info = entry.get("mpInfo")
    return str(entry.get("title") or (mp_info.get("title") if isinstance(mp_info, dict) else None) or fallback)


def _archive_complete(output_dir, path, digest, text):
    if path.stat().st_size <= 100:
        return False
    images = re.findall(r"!\[[^]]*\]\((" + re.escape(digest) + r"_images/[0-9]{2}\.(?:jpg|png|gif|webp))\)", text)
    expected = re.search(r"原文图片（(\d+) 张", text)
    return not (("微信公众号图片分享" in text or "_images/" in text) and (
        not images or not expected or len(images) != int(expected.group(1)) or not all(
            (output_dir / filename).is_file() and (output_dir / filename).stat().st_size >= 500
            for filename in images)))


def _existing_article(output_dir, digest):
    for path in output_dir.glob(digest + "_*.md"):
        text = path.read_text(encoding="utf-8")
        if _archive_complete(output_dir, path, digest, text):
            return path
    return None


def _existing_article_for_url(output_dir, url):
    """Recognize older reviewId-keyed archives without trusting an incomplete gallery."""
    for path in output_dir.glob("*.md"):
        digest = path.name.split("_", 1)[0]
        if not re.fullmatch(r"[0-9a-f]{12}", digest):
            continue
        text = path.read_text(encoding="utf-8")
        if ("> 来源：" + url) in text.splitlines()[:8] and _archive_complete(output_dir, path, digest, text):
            return path
    return None


def _save_article(output_dir, key, title, url, entry, result):
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    existing = _existing_article(output_dir, digest)
    if existing:
        return existing, False
    markdown = result.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise WeReadError("Article returned without Markdown; cannot save as a readable archive")
    assets = result.get("assets") or []
    if assets and result.get("reviewId"):
        source_digest = hashlib.sha256(result["reviewId"].encode("utf-8")).hexdigest()[:12]
        if source_digest != digest:
            markdown = markdown.replace(source_digest + "_images/", digest + "_images/")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (digest + "_" + _slug(result.get("title") or title) + ".md")
    metadata = [
        "# " + str(result.get("title") or title or "untitled"),
        "",
        "> 来源：" + url,
        "> 公众号：" + str(result.get("accountName") or ""),
        "> 发布时间：" + str(result.get("publishedAt") or entry.get("createTime") or ""),
        *(["> 内容渠道：" + result["contentSource"]] if result.get("contentSource") else []),
        "",
        "---",
        "",
    ]
    asset_dir = output_dir / (digest + "_images")
    created = []
    staged = []
    temporary_article = path.with_suffix(".md.part")
    try:
        if assets:
            asset_dir.mkdir(exist_ok=True)
            for asset in assets:
                filename, data = asset["filename"], asset["data"]
                if not re.fullmatch(r"[0-9]{2}\.(?:jpg|png|gif|webp)", filename) or not isinstance(data, bytes):
                    raise WeReadError("Invalid image-post asset", code="PICTURE_INVALID_IMAGE")
                destination = asset_dir / filename
                temporary = asset_dir / (filename + ".part")
                existed = destination.exists()
                temporary.write_bytes(data)
                staged.append(temporary)
                temporary.replace(destination)
                if not existed:
                    created.append(destination)
        temporary_article.write_text("\n".join(metadata) + markdown + "\n", encoding="utf-8")
        if temporary_article.stat().st_size <= 100:
            raise WeReadError("Saved article is unexpectedly short")
        temporary_article.replace(path)
    except (OSError, WeReadError) as exc:
        temporary_article.unlink(missing_ok=True)
        for temporary in staged:
            temporary.unlink(missing_ok=True)
        for file in created:
            file.unlink(missing_ok=True)
        if asset_dir.is_dir() and not any(asset_dir.iterdir()):
            asset_dir.rmdir()
        if isinstance(exc, WeReadError):
            raise
        raise WeReadError("Could not save article and all original images") from exc
    return path, True


