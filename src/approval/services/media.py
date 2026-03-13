"""S3 media service for the client approval portal.

Handles upload of images and videos to S3, including automatic WebP thumbnail
generation for images. All uploads follow a deterministic key structure:

    originals/{client_slug}/{asset_id}/v{version}/{filename}
    thumbnails/{client_slug}/{asset_id}/v{version}/{size}.webp
    videos/{client_slug}/{asset_id}/v{version}/{filename}
"""

import asyncio
import io
import logging
from functools import partial

import boto3
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported formats and size limits
# ---------------------------------------------------------------------------
SUPPORTED_IMAGES = {"jpg", "jpeg", "png", "webp", "gif", "tiff"}
SUPPORTED_VIDEOS = {"mp4", "mov", "avi", "webm"}
MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MB
THUMBNAIL_SIZES = {"thumb_400": 400, "thumb_800": 800}


class MediaService:
    """Manages S3 uploads and thumbnail generation for approval-portal media."""

    def __init__(self, bucket: str, region: str = "us-east-1"):
        self._bucket = bucket
        self._s3 = boto3.client("s3", region_name=region)

    # ------------------------------------------------------------------
    # Key builders
    # ------------------------------------------------------------------
    @staticmethod
    def _key(client_slug: str, asset_id: str, version: int, filename: str) -> str:
        """S3 object key for an original image upload."""
        return f"originals/{client_slug}/{asset_id}/v{version}/{filename}"

    @staticmethod
    def _thumb_key(client_slug: str, asset_id: str, version: int, size: int) -> str:
        """S3 object key for a WebP thumbnail."""
        return f"thumbnails/{client_slug}/{asset_id}/v{version}/{size}.webp"

    @staticmethod
    def _video_key(client_slug: str, asset_id: str, version: int, filename: str) -> str:
        """S3 object key for a video upload."""
        return f"videos/{client_slug}/{asset_id}/v{version}/{filename}"

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------
    async def upload_image(
        self,
        file_bytes: bytes,
        filename: str,
        client_slug: str,
        asset_id: str,
        version: int,
    ) -> dict:
        """Upload an original image and generate two WebP thumbnails (400px, 800px).

        Returns a dict with keys:
            original_url, thumbnail_url, width, height, file_size_bytes
        """
        file_size = len(file_bytes)
        if file_size > MAX_IMAGE_SIZE:
            raise ValueError(
                f"Image size {file_size} bytes exceeds maximum of {MAX_IMAGE_SIZE} bytes"
            )

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in SUPPORTED_IMAGES:
            raise ValueError(f"Unsupported image format: {ext}")

        loop = asyncio.get_running_loop()

        # Open image to get dimensions
        img = await loop.run_in_executor(None, partial(Image.open, io.BytesIO(file_bytes)))
        width, height = img.size

        # Upload original
        original_key = self._key(client_slug, asset_id, version, filename)
        content_type = _image_content_type(ext)
        await loop.run_in_executor(
            None,
            partial(
                self._s3.put_object,
                Bucket=self._bucket,
                Key=original_key,
                Body=file_bytes,
                ContentType=content_type,
            ),
        )

        # Generate and upload thumbnails
        thumb_url = None
        for label, max_dim in THUMBNAIL_SIZES.items():
            thumb_bytes = await loop.run_in_executor(
                None, partial(_generate_thumbnail, img, max_dim)
            )
            thumb_key = self._thumb_key(client_slug, asset_id, version, max_dim)
            await loop.run_in_executor(
                None,
                partial(
                    self._s3.put_object,
                    Bucket=self._bucket,
                    Key=thumb_key,
                    Body=thumb_bytes,
                    ContentType="image/webp",
                ),
            )
            # Use the 400px thumbnail as the default thumbnail_url
            if max_dim == 400:
                thumb_url = f"s3://{self._bucket}/{thumb_key}"

        original_url = f"s3://{self._bucket}/{original_key}"

        return {
            "original_url": original_url,
            "thumbnail_url": thumb_url,
            "width": width,
            "height": height,
            "file_size_bytes": file_size,
        }

    async def upload_video(
        self,
        file_bytes: bytes,
        filename: str,
        client_slug: str,
        asset_id: str,
        version: int,
    ) -> dict:
        """Upload a video file to S3.

        Returns a dict with keys:
            original_url, thumbnail_url (always None), file_size_bytes
        """
        file_size = len(file_bytes)
        if file_size > MAX_VIDEO_SIZE:
            raise ValueError(
                f"Video size {file_size} bytes exceeds maximum of {MAX_VIDEO_SIZE} bytes"
            )

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in SUPPORTED_VIDEOS:
            raise ValueError(f"Unsupported video format: {ext}")

        loop = asyncio.get_running_loop()

        video_key = self._video_key(client_slug, asset_id, version, filename)
        content_type = _video_content_type(ext)
        await loop.run_in_executor(
            None,
            partial(
                self._s3.put_object,
                Bucket=self._bucket,
                Key=video_key,
                Body=file_bytes,
                ContentType=content_type,
            ),
        )

        original_url = f"s3://{self._bucket}/{video_key}"

        return {
            "original_url": original_url,
            "thumbnail_url": None,
            "file_size_bytes": file_size,
        }

    # ------------------------------------------------------------------
    # Pre-signed URLs
    # ------------------------------------------------------------------
    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed GET URL for an S3 object.

        Args:
            key: The S3 object key.
            expires_in: URL validity in seconds (default 1 hour).

        Returns:
            A pre-signed URL string.
        """
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    # ------------------------------------------------------------------
    # File type detection
    # ------------------------------------------------------------------
    @staticmethod
    def detect_file_type(filename: str) -> tuple[str, str]:
        """Detect file type and format from a filename extension.

        Returns:
            A tuple of (file_type, file_format), e.g. ("image", "png") or
            ("video", "mp4").

        Raises:
            ValueError: If the file extension is not supported.
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in SUPPORTED_IMAGES:
            return ("image", ext)
        if ext in SUPPORTED_VIDEOS:
            return ("video", ext)
        raise ValueError(
            f"Unsupported file format: '{ext}'. "
            f"Supported images: {sorted(SUPPORTED_IMAGES)}, "
            f"videos: {sorted(SUPPORTED_VIDEOS)}"
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _generate_thumbnail(img: Image.Image, max_dim: int) -> bytes:
    """Resize an image so its longest side is *max_dim* and encode as WebP."""
    thumb = img.copy()
    thumb.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    # Convert RGBA/P to RGB for WebP compatibility
    if thumb.mode in ("RGBA", "P"):
        thumb = thumb.convert("RGB")
    buf = io.BytesIO()
    thumb.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def _image_content_type(ext: str) -> str:
    """Map image extension to MIME type."""
    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
        "tiff": "image/tiff",
    }
    return mapping.get(ext, "application/octet-stream")


def _video_content_type(ext: str) -> str:
    """Map video extension to MIME type."""
    mapping = {
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "webm": "video/webm",
    }
    return mapping.get(ext, "application/octet-stream")
