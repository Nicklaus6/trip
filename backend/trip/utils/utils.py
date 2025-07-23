import base64
from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image

from .. import __version__
from ..config import Settings

settings = Settings()


def generate_filename(format: str) -> str:
    return f"{uuid4()}.{format}"


def assets_folder_path() -> Path:
    return Path(settings.ASSETS_FOLDER)


def b64e(data: bytes) -> bytes:
    return base64.b64encode(data)


def b64img_decode(data: str) -> bytes:
    return (
        base64.b64decode(data.split(",", 1)[1]) if data.startswith("data:image/") else base64.b64decode(data)
    )


def remove_image(path: str):
    try:
        fpath = Path(assets_folder_path() / path)
        if not fpath.exists():
            # Skips missing file
            return
        fpath.unlink()
    except OSError as exc:
        raise Exception("Error deleting image:", exc, path)


def parse_str_or_date_to_date(cdate: str | date) -> date:
    if isinstance(cdate, str):
        try:
            return date.fromisoformat(cdate)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    return cdate


async def httpx_get(link: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": link,
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=5) as client:
            response = await client.get(link)
            response.raise_for_status()
            return response.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")


async def download_file(link: str, raise_on_error: bool = False) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": link,
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=5) as client:
            response = await client.get(link)
            response.raise_for_status()

            path = assets_folder_path() / generate_filename(link.split("?")[0].split(".")[-1])
            with open(path, "wb") as f:
                f.write(response.content)
                return f.name
    except Exception as e:
        if raise_on_error:
            raise HTTPException(status_code=400, detail=f"Failed to download file: {e}")
        return ""


async def check_update():
    url = "https://api.github.com/repos/itskovacs/trip/releases/latest"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()

        latest_version = response.json()["tag_name"]
        if __version__ != latest_version:
            return latest_version

        return None

    except Exception:
        raise HTTPException(status_code=503, detail="Couldn't verify for update")


def patch_image(fp: str, size: int = 400) -> bool:
    try:
        with Image.open(fp) as im:
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")

            # Resize and crop to square of size x size
            if size > 0:
                im_ratio = im.width / im.height

                if im_ratio > 1:
                    new_height = size
                    new_width = int(size * im_ratio)
                else:
                    new_width = size
                    new_height = int(size / im_ratio)

                im = im.resize((new_width, new_height), Image.LANCZOS)

                left = (im.width - size) // 2
                top = (im.height - size) // 2
                right = left + size
                bottom = top + size

                im = im.crop((left, top, right, bottom))

            im.save(fp)
            return True

    except Exception:
        ...
    return False


def save_image_to_file(content: bytes, size: int = 600) -> str:
    try:
        with Image.open(BytesIO(content)) as im:
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")

            if size > 0:  # Crop as square of (size * size)
                im_ratio = im.width / im.height
                target_ratio = 1  # Square ratio is 1

                if im_ratio > target_ratio:
                    new_height = size
                    new_width = int(new_height * im_ratio)
                else:
                    new_width = size
                    new_height = int(new_width / im_ratio)

                im = im.resize((new_width, new_height), Image.LANCZOS)

                left = (im.width - size) // 2
                top = (im.height - size) // 2
                right = left + size
                bottom = top + size

                im = im.crop((left, top, right, bottom))

            if content.startswith(b"\x89PNG"):
                image_ext = "png"
            elif content.startswith(b"\xff\xd8"):
                image_ext = "jpeg"
            elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
                image_ext = "webp"
            else:
                raise ValueError("Unsupported image format")

            filename = generate_filename(image_ext)
            filepath = assets_folder_path() / filename
            im.save(filepath)

            return filename

    except Exception:
        ...
    return ""
