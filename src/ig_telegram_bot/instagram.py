from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import instaloader
from instaloader.exceptions import (
    ConnectionException,
    LoginRequiredException,
    PrivateProfileNotFollowedException,
    QueryReturnedNotFoundException,
    TooManyRequestsException,
)

_INSTAGRAM_LINK = re.compile(
    r"https?://(?:(?:www|m)\.)?instagram\.com/"
    r"(?:p|reel|reels|tv)/(?P<shortcode>[A-Za-z0-9_-]{5,30})"
    r"(?=[/?#\s]|$)",
    flags=re.IGNORECASE,
)
_MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4"}


class InvalidInstagramLink(ValueError):
    """The message does not contain a supported Instagram post URL."""


class InstagramDownloadError(RuntimeError):
    """A user-facing Instagram download failure."""


@dataclass(frozen=True, slots=True)
class DownloadResult:
    shortcode: str
    source_url: str
    owner_username: str
    caption: str
    media_paths: tuple[Path, ...]


def extract_shortcode(text: str) -> str:
    """Return a validated shortcode from a public post/reel URL in *text*."""
    match = _INSTAGRAM_LINK.search(text.strip())
    if not match:
        raise InvalidInstagramLink("لینک معتبر پست یا ریلز اینستاگرام پیدا نشد.")
    return match.group("shortcode")


class InstagramDownloader:
    """Download one public post without using Instagram credentials."""

    def download(self, shortcode: str, target_directory: Path) -> DownloadResult:
        target_directory.mkdir(parents=True, exist_ok=True)
        loader = instaloader.Instaloader(
            quiet=True,
            dirname_pattern="{target}",
            filename_pattern="{shortcode}_{date_utc}_UTC",
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",
            max_connection_attempts=3,
            request_timeout=30,
            resume_prefix=None,
            sanitize_paths=True,
        )

        try:
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            owner_username = post.owner_username or "unknown"
            caption = post.caption or ""
            loader.download_post(post, target=target_directory)
        except (PrivateProfileNotFollowedException, LoginRequiredException) as exc:
            raise InstagramDownloadError(
                "این محتوا خصوصی است یا Instagram برای مشاهده آن ورود به حساب می‌خواهد."
            ) from exc
        except QueryReturnedNotFoundException as exc:
            raise InstagramDownloadError(
                "پست پیدا نشد؛ ممکن است حذف شده، خصوصی باشد یا لینک اشتباه باشد."
            ) from exc
        except TooManyRequestsException as exc:
            raise InstagramDownloadError(
                "Instagram موقتاً تعداد درخواست‌ها را محدود کرده است؛ "
                "چند دقیقه بعد دوباره امتحان کنید."
            ) from exc
        except ConnectionException as exc:
            raise InstagramDownloadError(
                "ارتباط با Instagram برقرار نشد؛ کمی بعد دوباره امتحان کنید."
            ) from exc
        except instaloader.InstaloaderException as exc:
            raise InstagramDownloadError(
                "Instagram پاسخ قابل استفاده‌ای نداد؛ ممکن است ساختار سایت تغییر کرده باشد."
            ) from exc
        finally:
            loader.close()

        media_paths = tuple(
            sorted(
                (
                    path
                    for path in target_directory.iterdir()
                    if path.is_file() and path.suffix.lower() in _MEDIA_EXTENSIONS
                ),
                key=_natural_filename_key,
            )
        )
        if not media_paths:
            raise InstagramDownloadError("فایل تصویری یا ویدئویی قابل ارسال پیدا نشد.")

        return DownloadResult(
            shortcode=shortcode,
            source_url=f"https://www.instagram.com/p/{shortcode}/",
            owner_username=owner_username,
            caption=caption,
            media_paths=media_paths,
        )


def _natural_filename_key(path: Path) -> tuple[tuple[int, int | str], ...]:
    """Keep carousel items 2..10 in numeric rather than lexical order."""
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", path.name)
        if part
    )
