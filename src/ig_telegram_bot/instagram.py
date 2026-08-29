from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
_SOCLIP_ENDPOINT = "https://api.soclip.dev/v1/media"
_SOCLIP_RESPONSE_LIMIT = 1024 * 1024
_SUPPORTED_SOCLIP_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "mp4"}


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
    """Download public Instagram posts/reels and active public stories."""

    def __init__(
        self,
        story_session: StorySession | None = None,
        soclip_api_key: str = "",
        max_download_bytes: int = 49 * 1024 * 1024,
    ) -> None:
        self._story_session = story_session
        self._soclip_api_key = soclip_api_key.strip()
        self._max_download_bytes = max_download_bytes

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
        if self._soclip_api_key:
            return self._download_story_hosted(target, target_directory)

        session = self._story_session
        if session is not None and session.configured:
            return self._download_story_with_session(target, target_directory)

        raise InstagramDownloadError(
            "دانلود استوری هنوز فعال نشده است؛ مدیر ربات فقط باید SOCLIP_API_KEY را "
            "در تنظیمات سرور وارد کند."
        )

    def _download_story_hosted(
        self,
        target: InstagramTarget,
        target_directory: Path,
    ) -> DownloadResult:
        source_url = (
            f"https://www.instagram.com/stories/{target.username}/{target.media_id}/"
        )
        request = Request(
            _SOCLIP_ENDPOINT,
            data=json.dumps({"url": source_url}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._soclip_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "instagram-telegram-bot/4",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=35) as response:
                raw = response.read(_SOCLIP_RESPONSE_LIMIT + 1)
        except HTTPError as exc:
            self._raise_soclip_http_error(exc)
        except URLError as exc:
            raise InstagramDownloadError(
                "سرویس دریافت استوری موقتاً در دسترس نیست؛ کمی بعد دوباره امتحان کنید."
            ) from exc

        if len(raw) > _SOCLIP_RESPONSE_LIMIT:
            raise InstagramDownloadError("پاسخ سرویس استوری نامعتبر بود.")

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InstagramDownloadError("پاسخ سرویس استوری قابل پردازش نبود.") from exc

        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise InstagramDownloadError(
                "این استوری قابل دریافت نیست؛ ممکن است منقضی، حذف یا غیرعمومی باشد."
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise InstagramDownloadError("سرویس استوری فایل قابل استفاده‌ای برنگرداند.")

        medias = data.get("medias")
        if not isinstance(medias, list):
            raise InstagramDownloadError("فایل استوری در پاسخ سرویس پیدا نشد.")

        media = _select_soclip_media(medias)
        media_url = str(media.get("url", "")).strip()
        extension = _normalize_media_extension(str(media.get("ext", "")), media_url)
        if not media_url or urlparse(media_url).scheme.lower() != "https":
            raise InstagramDownloadError("آدرس فایل استوری نامعتبر بود.")

        target_directory.mkdir(parents=True, exist_ok=True)
        output_path = target_directory / f"story_{target.media_id}.{extension}"
        self._download_remote_media(media_url, output_path)

        return DownloadResult(
            shortcode=str(target.media_id),
            source_url=source_url,
            owner_username=target.username,
            caption="",
            media_paths=(output_path,),
        )

    def _download_remote_media(self, media_url: str, output_path: Path) -> None:
        request = Request(
            media_url,
            headers={"User-Agent": "Mozilla/5.0 instagram-telegram-bot/4"},
        )
        try:
            with urlopen(request, timeout=45) as response:
                final_url = response.geturl()
                if urlparse(final_url).scheme.lower() != "https":
                    raise InstagramDownloadError("آدرس نهایی فایل استوری امن نیست.")

                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > self._max_download_bytes:
                            raise InstagramDownloadError(
                                "حجم این استوری از سقف قابل ارسال Telegram بیشتر است."
                            )
                    except ValueError:
                        pass

                total = 0
                with output_path.open("wb") as destination:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > self._max_download_bytes:
                            raise InstagramDownloadError(
                                "حجم این استوری از سقف قابل ارسال Telegram بیشتر است."
                            )
                        destination.write(chunk)
        except InstagramDownloadError:
            output_path.unlink(missing_ok=True)
            raise
        except (HTTPError, URLError, OSError) as exc:
            output_path.unlink(missing_ok=True)
            raise InstagramDownloadError(
                "دریافت فایل استوری از CDN کامل نشد؛ دوباره امتحان کنید."
            ) from exc

    @staticmethod
    def _raise_soclip_http_error(exc: HTTPError) -> None:
        if exc.code in {401, 403}:
            raise InstagramDownloadError(
                "کلید سرویس Story نامعتبر است؛ مدیر ربات باید SOCLIP_API_KEY را بررسی کند."
            ) from exc
        if exc.code == 402:
            raise InstagramDownloadError(
                "اعتبار رایگان سرویس Story تمام شده است؛ مدیر ربات باید اعتبار حساب را بررسی کند."
            ) from exc
        if exc.code == 429:
            raise InstagramDownloadError(
                "سرویس Story موقتاً درخواست‌ها را محدود کرده است؛ کمی بعد دوباره امتحان کنید."
            ) from exc
        if exc.code in {400, 404, 410, 422}:
            raise InstagramDownloadError(
                "این استوری قابل دریافت نیست؛ ممکن است منقضی، حذف یا غیرعمومی باشد."
            ) from exc
        raise InstagramDownloadError(
            "سرویس دریافت استوری با خطا روبه‌رو شد؛ کمی بعد دوباره امتحان کنید."
        ) from exc

    def _download_story_with_session(
        self,
        target: InstagramTarget,
        target_directory: Path,
    ) -> DownloadResult:
        session = self._story_session
        if session is None or not session.configured:
            raise InstagramDownloadError("سشن Instagram برای Story تنظیم نشده است.")

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


def _select_soclip_media(medias: list[Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for item in medias:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        ext = _normalize_media_extension(str(item.get("ext", "")), url, strict=False)
        if not url or ext not in _SUPPORTED_SOCLIP_EXTENSIONS:
            continue
        candidates.append(item)

    if not candidates:
        raise InstagramDownloadError("سرویس Story هیچ فایل قابل ارسال برنگرداند.")

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        ext = _normalize_media_extension(
            str(item.get("ext", "")),
            str(item.get("url", "")),
            strict=False,
        )
        is_video = 1 if ext == "mp4" else 0
        width = _safe_int(item.get("width"))
        height = _safe_int(item.get("height"))
        return (is_video, width * height, height)

    return max(candidates, key=score)


def _normalize_media_extension(ext: str, url: str, *, strict: bool = True) -> str:
    normalized = ext.strip().lower().lstrip(".")
    if not normalized:
        suffix = Path(urlparse(url).path).suffix.lower().lstrip(".")
        normalized = suffix
    if normalized == "jpeg":
        normalized = "jpg"
    if strict and normalized not in _SUPPORTED_SOCLIP_EXTENSIONS:
        raise InstagramDownloadError("قالب فایل Story پشتیبانی نمی‌شود.")
    return normalized


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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
