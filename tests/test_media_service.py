"""Tests for the S3 media service (src/approval/services/media.py).

All S3 interactions are mocked using unittest.mock.patch so no real AWS
credentials or network access are required. PIL Image operations use small
in-memory test images.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.approval.services.media import (
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
    SUPPORTED_IMAGES,
    SUPPORTED_VIDEOS,
    THUMBNAIL_SIZES,
    MediaService,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

BUCKET = "app-approval-media"
REGION = "us-east-1"
CLIENT_SLUG = "client_alpha"
ASSET_ID = "abc-123"
VERSION = 1


def _make_png_bytes(width: int = 200, height: int = 150) -> bytes:
    """Create a minimal valid PNG image in memory."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_rgba_png_bytes(width: int = 200, height: int = 150) -> bytes:
    """Create a minimal valid RGBA PNG image in memory."""
    img = Image.new("RGBA", (width, height), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_video_bytes(size: int = 1024) -> bytes:
    """Create fake video bytes (just random-ish data)."""
    return b"\x00\x00\x00\x1c" + b"\x00" * (size - 4)


@pytest.fixture
def mock_s3():
    """Patch boto3.client so no real S3 calls are made."""
    with patch("src.approval.services.media.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.generate_presigned_url.return_value = (
            "https://app-approval-media.s3.amazonaws.com/signed-url"
        )
        yield mock_client


@pytest.fixture
def service(mock_s3):
    """MediaService instance with mocked S3."""
    return MediaService(bucket=BUCKET, region=REGION)


# ===========================================================================
# S3 key generation
# ===========================================================================


class TestKeyGeneration:
    """Verify deterministic S3 key structures."""

    def test_original_key_format(self):
        key = MediaService._key(CLIENT_SLUG, ASSET_ID, VERSION, "photo.png")
        assert key == "originals/client_alpha/abc-123/v1/photo.png"

    def test_thumbnail_key_format(self):
        key = MediaService._thumb_key(CLIENT_SLUG, ASSET_ID, VERSION, 400)
        assert key == "thumbnails/client_alpha/abc-123/v1/400.webp"

    def test_thumbnail_key_800(self):
        key = MediaService._thumb_key(CLIENT_SLUG, ASSET_ID, VERSION, 800)
        assert key == "thumbnails/client_alpha/abc-123/v1/800.webp"

    def test_video_key_format(self):
        key = MediaService._video_key(CLIENT_SLUG, ASSET_ID, VERSION, "clip.mp4")
        assert key == "videos/client_alpha/abc-123/v1/clip.mp4"

    def test_key_with_different_version(self):
        key = MediaService._key("client_delta", "xyz-789", 3, "banner.jpg")
        assert key == "originals/client_delta/xyz-789/v3/banner.jpg"

    def test_video_key_with_different_client(self):
        key = MediaService._video_key("client_gamma", "def-456", 2, "reel.mov")
        assert key == "videos/client_gamma/def-456/v2/reel.mov"


# ===========================================================================
# upload_image
# ===========================================================================


class TestUploadImage:
    """upload_image: uploads original + 2 thumbnails to S3."""

    @pytest.mark.asyncio
    async def test_calls_s3_put_object_three_times(self, service, mock_s3):
        """One call for original + two for thumbnails = 3 put_object calls."""
        png_bytes = _make_png_bytes()
        result = await service.upload_image(
            file_bytes=png_bytes,
            filename="photo.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        assert mock_s3.put_object.call_count == 3
        assert result is not None

    @pytest.mark.asyncio
    async def test_returns_correct_metadata(self, service, mock_s3):
        png_bytes = _make_png_bytes(width=1920, height=1080)
        result = await service.upload_image(
            file_bytes=png_bytes,
            filename="banner.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["file_size_bytes"] == len(png_bytes)
        assert "original_url" in result
        assert "thumbnail_url" in result
        assert result["original_url"].startswith(f"s3://{BUCKET}/originals/")
        assert result["thumbnail_url"].startswith(f"s3://{BUCKET}/thumbnails/")

    @pytest.mark.asyncio
    async def test_original_key_in_put_object(self, service, mock_s3):
        png_bytes = _make_png_bytes()
        await service.upload_image(
            file_bytes=png_bytes,
            filename="photo.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        # First call is the original
        call_args = mock_s3.put_object.call_args_list[0]
        assert call_args.kwargs["Key"] == "originals/client_alpha/abc-123/v1/photo.png"
        assert call_args.kwargs["Bucket"] == BUCKET
        assert call_args.kwargs["ContentType"] == "image/png"

    @pytest.mark.asyncio
    async def test_thumbnail_keys_in_put_object(self, service, mock_s3):
        png_bytes = _make_png_bytes()
        await service.upload_image(
            file_bytes=png_bytes,
            filename="photo.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        # Thumbnail calls are the 2nd and 3rd
        thumb_keys = [
            mock_s3.put_object.call_args_list[i].kwargs["Key"]
            for i in (1, 2)
        ]
        expected = {
            f"thumbnails/{CLIENT_SLUG}/{ASSET_ID}/v{VERSION}/{size}.webp"
            for size in THUMBNAIL_SIZES.values()
        }
        assert set(thumb_keys) == expected

    @pytest.mark.asyncio
    async def test_thumbnails_are_webp(self, service, mock_s3):
        png_bytes = _make_png_bytes()
        await service.upload_image(
            file_bytes=png_bytes,
            filename="photo.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        for i in (1, 2):
            assert mock_s3.put_object.call_args_list[i].kwargs["ContentType"] == "image/webp"

    @pytest.mark.asyncio
    async def test_thumbnail_url_is_400px(self, service, mock_s3):
        png_bytes = _make_png_bytes()
        result = await service.upload_image(
            file_bytes=png_bytes,
            filename="photo.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        assert "/400.webp" in result["thumbnail_url"]

    @pytest.mark.asyncio
    async def test_rejects_oversized_image(self, service, mock_s3):
        huge = b"\x00" * (MAX_IMAGE_SIZE + 1)
        with pytest.raises(ValueError, match="exceeds maximum"):
            await service.upload_image(
                file_bytes=huge,
                filename="huge.png",
                client_slug=CLIENT_SLUG,
                asset_id=ASSET_ID,
                version=VERSION,
            )
        mock_s3.put_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_unsupported_image_format(self, service, mock_s3):
        png_bytes = _make_png_bytes()
        with pytest.raises(ValueError, match="Unsupported image format"):
            await service.upload_image(
                file_bytes=png_bytes,
                filename="photo.bmp",
                client_slug=CLIENT_SLUG,
                asset_id=ASSET_ID,
                version=VERSION,
            )
        mock_s3.put_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_rgba_image(self, service, mock_s3):
        """RGBA images should be converted to RGB for WebP thumbnails."""
        rgba_bytes = _make_rgba_png_bytes()
        result = await service.upload_image(
            file_bytes=rgba_bytes,
            filename="overlay.png",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        assert mock_s3.put_object.call_count == 3
        assert result["width"] == 200
        assert result["height"] == 150

    @pytest.mark.asyncio
    async def test_jpeg_content_type(self, service, mock_s3):
        """JPEG files should have the correct content type."""
        img = Image.new("RGB", (100, 100), color=(0, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpg_bytes = buf.getvalue()

        await service.upload_image(
            file_bytes=jpg_bytes,
            filename="photo.jpg",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        call_args = mock_s3.put_object.call_args_list[0]
        assert call_args.kwargs["ContentType"] == "image/jpeg"


# ===========================================================================
# upload_video
# ===========================================================================


class TestUploadVideo:
    """upload_video: uploads a single video file to S3."""

    @pytest.mark.asyncio
    async def test_calls_s3_put_object_once(self, service, mock_s3):
        video_bytes = _make_video_bytes()
        result = await service.upload_video(
            file_bytes=video_bytes,
            filename="reel.mp4",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        mock_s3.put_object.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_returns_correct_metadata(self, service, mock_s3):
        video_bytes = _make_video_bytes(size=5000)
        result = await service.upload_video(
            file_bytes=video_bytes,
            filename="clip.mp4",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        assert result["original_url"].startswith(f"s3://{BUCKET}/videos/")
        assert result["thumbnail_url"] is None
        assert result["file_size_bytes"] == 5000

    @pytest.mark.asyncio
    async def test_video_key_in_put_object(self, service, mock_s3):
        video_bytes = _make_video_bytes()
        await service.upload_video(
            file_bytes=video_bytes,
            filename="promo.mov",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs["Key"] == "videos/client_alpha/abc-123/v1/promo.mov"
        assert call_args.kwargs["ContentType"] == "video/quicktime"

    @pytest.mark.asyncio
    async def test_rejects_oversized_video(self, service, mock_s3):
        huge = b"\x00" * (MAX_VIDEO_SIZE + 1)
        with pytest.raises(ValueError, match="exceeds maximum"):
            await service.upload_video(
                file_bytes=huge,
                filename="huge.mp4",
                client_slug=CLIENT_SLUG,
                asset_id=ASSET_ID,
                version=VERSION,
            )
        mock_s3.put_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_unsupported_video_format(self, service, mock_s3):
        video_bytes = _make_video_bytes()
        with pytest.raises(ValueError, match="Unsupported video format"):
            await service.upload_video(
                file_bytes=video_bytes,
                filename="clip.flv",
                client_slug=CLIENT_SLUG,
                asset_id=ASSET_ID,
                version=VERSION,
            )
        mock_s3.put_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_mp4_content_type(self, service, mock_s3):
        video_bytes = _make_video_bytes()
        await service.upload_video(
            file_bytes=video_bytes,
            filename="clip.mp4",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs["ContentType"] == "video/mp4"

    @pytest.mark.asyncio
    async def test_webm_content_type(self, service, mock_s3):
        video_bytes = _make_video_bytes()
        await service.upload_video(
            file_bytes=video_bytes,
            filename="clip.webm",
            client_slug=CLIENT_SLUG,
            asset_id=ASSET_ID,
            version=VERSION,
        )
        call_args = mock_s3.put_object.call_args
        assert call_args.kwargs["ContentType"] == "video/webm"


# ===========================================================================
# generate_presigned_url
# ===========================================================================


class TestGeneratePresignedUrl:
    """generate_presigned_url: delegates to S3 client correctly."""

    def test_calls_s3_generate_presigned_url(self, service, mock_s3):
        key = "originals/client_alpha/abc-123/v1/photo.png"
        url = service.generate_presigned_url(key)
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600,
        )
        assert url == "https://app-approval-media.s3.amazonaws.com/signed-url"

    def test_custom_expiration(self, service, mock_s3):
        key = "videos/client_alpha/abc-123/v1/clip.mp4"
        service.generate_presigned_url(key, expires_in=7200)
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=7200,
        )

    def test_returns_string(self, service, mock_s3):
        url = service.generate_presigned_url("some/key.png")
        assert isinstance(url, str)


# ===========================================================================
# detect_file_type
# ===========================================================================


class TestDetectFileType:
    """detect_file_type: static method for file classification."""

    @pytest.mark.parametrize(
        "filename,expected_type,expected_format",
        [
            ("photo.jpg", "image", "jpg"),
            ("photo.jpeg", "image", "jpeg"),
            ("banner.png", "image", "png"),
            ("icon.webp", "image", "webp"),
            ("anim.gif", "image", "gif"),
            ("scan.tiff", "image", "tiff"),
            ("clip.mp4", "video", "mp4"),
            ("reel.mov", "video", "mov"),
            ("old.avi", "video", "avi"),
            ("stream.webm", "video", "webm"),
        ],
    )
    def test_supported_formats(self, filename, expected_type, expected_format):
        file_type, file_format = MediaService.detect_file_type(filename)
        assert file_type == expected_type
        assert file_format == expected_format

    def test_case_insensitive(self):
        file_type, file_format = MediaService.detect_file_type("PHOTO.PNG")
        assert file_type == "image"
        assert file_format == "png"

    def test_mixed_case(self):
        file_type, file_format = MediaService.detect_file_type("Video.Mp4")
        assert file_type == "video"
        assert file_format == "mp4"

    @pytest.mark.parametrize(
        "filename",
        [
            "document.pdf",
            "spreadsheet.xlsx",
            "archive.zip",
            "readme.txt",
            "style.css",
            "noextension",
            "photo.bmp",
            "clip.flv",
        ],
    )
    def test_raises_for_unsupported(self, filename):
        with pytest.raises(ValueError, match="Unsupported file format"):
            MediaService.detect_file_type(filename)

    def test_error_message_includes_supported_formats(self):
        with pytest.raises(ValueError) as exc_info:
            MediaService.detect_file_type("readme.txt")
        msg = str(exc_info.value)
        assert "Supported images" in msg
        assert "videos" in msg


# ===========================================================================
# Constants verification
# ===========================================================================


class TestConstants:
    """Verify module-level constants are correctly defined."""

    def test_supported_images(self):
        assert SUPPORTED_IMAGES == {"jpg", "jpeg", "png", "webp", "gif", "tiff"}

    def test_supported_videos(self):
        assert SUPPORTED_VIDEOS == {"mp4", "mov", "avi", "webm"}

    def test_max_image_size(self):
        assert MAX_IMAGE_SIZE == 50 * 1024 * 1024

    def test_max_video_size(self):
        assert MAX_VIDEO_SIZE == 500 * 1024 * 1024

    def test_thumbnail_sizes(self):
        assert THUMBNAIL_SIZES == {"thumb_400": 400, "thumb_800": 800}
        assert len(THUMBNAIL_SIZES) == 2


# ===========================================================================
# Service initialization
# ===========================================================================


class TestMediaServiceInit:
    """Verify MediaService constructor wires up S3 client."""

    def test_stores_bucket(self, service):
        assert service._bucket == BUCKET

    def test_default_region(self, mock_s3):
        svc = MediaService(bucket="test-bucket")
        assert svc._bucket == "test-bucket"

    def test_s3_client_created(self, mock_s3):
        """boto3.client is called with the correct region."""
        with patch("src.approval.services.media.boto3") as mock_boto3:
            MediaService(bucket="b", region="eu-west-1")
            mock_boto3.client.assert_called_once_with("s3", region_name="eu-west-1")
