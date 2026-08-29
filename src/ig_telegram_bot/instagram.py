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

_POST_LINK = re.compile(
    r"https?://(?:(?:www|m)\.)?instagram\.com/"
    r"(?:p|reel|reels|tv)/(?P<shortcode>[A-Za-z0-9_-]{5,30})"
    r"(?=[/?#\s]|$)",
    flags=re.IGNORECASE,
)
_STORY_LINK = re.compile(
    r"https?://(?:(?:www|m)\.)?instagram\.com/stories/"
    r"(?P<username>[A-Za-z0-9._]{1,30})/(?P<media_id>\d+)"
    r"(?=[/?#\s]|$)",
    flags=re.IGNORECASE,
)
_MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4"}


class InvalidInstagramLink(ValueError):
    """The message does not contain a supported Instagram URL."""


class InstagramDownloadError(RuntimeError):
    """A user-facing Instagram download failure."""


@dataclass(frozen=True, slots=True)
class InstagramTarget:
    kind: str
    shortcode: str = ""
    username: str = ""
    media_id: int = 0

    @property
    def is_story(self) -> bool:
        return self.kind == "story"


@dataclass(frozen=True, slots=True)
class StorySession:
    username: str
    sessionid: str
    csrftoken: str
    ds_user_id: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.username and self.sessionid and self.csrftoken)

    def cookies(self) -> dict[str, str]:
        cookies = {
            "sessionid": self.sessionid,
            "csrftoken": self.csrftoken,
        }
        if self.ds_user_id:
            cookies["ds_user_id"] = self.ds_user_id
        return cookies


@dataclass(frozen=True, slots=True)
class DownloadResult:
    shortcode: str
    source_url: str
    owner_username: str
    caption: str
    media_paths: tuple[Path, ...]


def parse_instagram_target(text: str) -> InstagramTarget:
    """Parse a supported post, reel, or story URL from *text*."""
    cleaned = text.strip()

    story_match = _STORY_LINK.search(cleaned)
    if story_match:
        return InstagramTarget(
            kind="story",
            username=story_match.group("username"),
            media_id=int(story_match.group("media_id")),
        )

    post_match = _POST_LINK.search(cleaned)
    if post_match:
        return InstagramTarget(kind="post", shortcode=post_match.group("shortcode"))

    raise InvalidInstagramLink("لینک معتبر پست، ریلز یا استوری Instagram پیدا نشد.")


def extract_shortcode(text: str) -> str:
    """Backward-compatible helper that extracts only post/reel shortcodes."""
    target = parse_instagram_target(text)
    if target.is_story:
        raise InvalidInstagramLink("این لینک مربوط به استوری است و shortcode پست ندارد.")
    return target.shortcode


class InstagramDownloader:
    """Download public Instagram posts/reels and public stories."""

    def __init__(self, story_session: StorySession | None = None) -> None:
        self._story_session = story_session

    def download(
        self,
        target: InstagramTarget | str,
        target_directory: Path,
    ) -> DownloadResult:
        if isinstance(target, str):
            target = InstagramTarget(kind="post", shortcode=target)
        if target.is_story:
            return self._download_story(target, target_directory)
        return self._download_post(target.shortcode, target_directory)

    def _new_loader(self) -> instaloader.Instaloader:
        return instaloader.Instaloader(
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

    def _download_post(self, shortcode: str, target_directory: Path) -> DownloadResult:
        target_directory.mkdir(parents=True, exist_ok=True)
        loader = self._new_loader()

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

        media_paths = _collect_media_paths(target_directory)
        if not media_paths:
            raise InstagramDownloadError("فایل تصویری یا ویدئویی قابل ارسال پیدا نشد.")

        return DownloadResult(
            shortcode=shortcode,
            source_url=f"https://www.instagram.com/p/{shortcode}/",
            owner_username=owner_username,
            caption=caption,
            media_paths=media_paths,
        )

    def _download_story(
        self,
        target: InstagramTarget,
        target_directory: Path,
    ) -> DownloadResult:
        session = self._story_session
        if session is None or not session.configured:
            raise InstagramDownloadError(
                "دانلود استوری روی سرور هنوز فعال نشده است؛ "
                "سشن Instagram باید در تنظیمات امن سرور ثبت شود."
            )

        target_directory.mkdir(parents=True, exist_ok=True)
        loader = self._new_loader()

        try:
            loader.load_session(session.username, session.cookies())
            if loader.test_login() is None:
                raise InstagramDownloadError(
                    "سشن Instagram منقضی یا نامعتبر است؛ مدیر ربات باید آن را به‌روزرسانی کند."
                )

            profile = instaloader.Profile.from_username(loader.context, target.username)
            if profile.is_private:
                raise InstagramDownloadError(
                    "این ربات فقط استوری حساب‌های عمومی Instagram را دریافت می‌کند."
                )

            found = False
            for story in loader.get_stories(userids=[profile.userid]):
                for item in story.get_items():
                    if item.mediaid == target.media_id:
                        loader.download_storyitem(item, target=target_directory)
                        found = True
                        break
                if found:
                    break

            if not found:
                raise InstagramDownloadError(
                    "استوری پیدا نشد؛ ممکن است منقضی یا حذف شده باشد."
                )
        except InstagramDownloadError:
            raise
        except (PrivateProfileNotFollowedException, LoginRequiredException) as exc:
            raise InstagramDownloadError(
                "Instagram برای این استوری دسترسی لازم را نداد."
            ) from exc
        except TooManyRequestsException as exc:
            raise InstagramDownloadError(
                "Instagram موقتاً درخواست‌های استوری را محدود کرده است؛ "
                "چند دقیقه بعد دوباره امتحان کنید."
            ) from exc
        except ConnectionException as exc:
            raise InstagramDownloadError(
                "ارتباط با Instagram برای دریافت استوری برقرار نشد."
            ) from exc
        except instaloader.InstaloaderException as exc:
            raise InstagramDownloadError(
                "Instagram پاسخ قابل استفاده‌ای برای این استوری نداد."
            ) from exc
        finally:
            loader.close()

        media_paths = _collect_media_paths(target_directory)
        if not media_paths:
            raise InstagramDownloadError("فایل استوری قابل ارسال پیدا نشد.")

        return DownloadResult(
            shortcode=str(target.media_id),
            source_url=(
                f"https://www.instagram.com/stories/{target.username}/{target.media_id}/"
            ),
            owner_username=target.username,
            caption="",
            media_paths=media_paths,
        )


def _collect_media_paths(target_directory: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                path
                for path in target_directory.iterdir()
                if path.is_file() and path.suffix.lower() in _MEDIA_EXTENSIONS
            ),
            key=_natural_filename_key,
        )
    )


def _natural_filename_key(path: Path) -> tuple[tuple[int, int | str], ...]:
    """Keep carousel items 2..10 in numeric rather than lexical order."""
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", path.name)
        if part
    )
