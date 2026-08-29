from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO

from telegram import InputMediaPhoto, InputMediaVideo, Message, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, NetworkError, TelegramError, TimedOut
from telegram.ext import ContextTypes

from .config import Settings
from .instagram import (
    DownloadResult,
    InstagramDownloader,
    InstagramDownloadError,
    InvalidInstagramLink,
    StorySession,
    parse_instagram_target,
)
from .rate_limit import SlidingWindowRateLimiter

LOGGER = logging.getLogger(__name__)
PHOTO_UPLOAD_LIMIT = 10 * 1024 * 1024
MEDIA_GROUP_LIMIT = 10
CAPTION_SAFE_LIMIT = 1000

START_TEXT = """سلام! 👋

لینک یک پست، ریلز، آلبوم یا استوری عمومی Instagram را بفرستید تا فایل آن را برایتان ارسال کنم.

نمونه پست/ریلز:
https://www.instagram.com/reel/SHORTCODE/

نمونه استوری:
https://www.instagram.com/stories/username/123456789/

🔒 فقط محتوای عمومی پشتیبانی می‌شود."""

HELP_TEXT = """راهنما 📥

۱) لینک کامل پست، ریلز، آلبوم یا استوری عمومی Instagram را کپی کنید.
۲) لینک را در یک پیام برای ربات بفرستید.
۳) تا پایان دریافت و ارسال فایل صبر کنید.

استوری باید هنوز فعال باشد؛ استوری حذف‌شده یا منقضی قابل دریافت نیست.
محتوای حساب خصوصی پشتیبانی نمی‌شود.
فقط از محتوایی استفاده کنید که اجازهٔ ذخیره یا بازنشر آن را دارید."""


def build_caption(result: DownloadResult) -> str:
    owner = result.owner_username.strip().lstrip("@") or "unknown"
    header = f"✅ دریافت شد\n👤 @{owner}"
    if not result.caption.strip():
        return header

    available = CAPTION_SAFE_LIMIT - len(header) - 2
    caption = result.caption.strip()
    if len(caption) > available:
        caption = f"{caption[: max(0, available - 1)].rstrip()}…"
    return f"{header}\n\n{caption}"


class InstagramBotService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        story_session = StorySession(
            username=settings.instagram_username,
            sessionid=settings.instagram_sessionid,
            csrftoken=settings.instagram_csrftoken,
            ds_user_id=settings.instagram_ds_user_id,
        )
        self._downloader = InstagramDownloader(story_session=story_session)
        self._download_slots = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._rate_limiter = SlidingWindowRateLimiter(settings.max_requests_per_minute)
        self._active_users: set[int] = set()
        self._active_users_lock = asyncio.Lock()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.effective_message:
            await update.effective_message.reply_text(START_TEXT)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.effective_message:
            await update.effective_message.reply_text(HELP_TEXT)

    async def privacy(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        if update.effective_message:
            await update.effective_message.reply_text(
                "🔐 ربات فقط لینک ارسالی را هنگام پردازش استفاده می‌کند. فایل‌ها در پوشهٔ موقت "
                "قرار می‌گیرند و بلافاصله پس از ارسال حذف می‌شوند. برای استوری، سشن امن حساب "
                "مدیر فقط روی سرور نگهداری می‌شود و اطلاعات ورود کاربران درخواست نمی‌شود."
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        message = update.effective_message
        user = update.effective_user
        if not message or not message.text or not user:
            return

        try:
            target = parse_instagram_target(message.text)
        except InvalidInstagramLink:
            await message.reply_text(
                "لطفاً لینک کامل پست، ریلز یا استوری عمومی Instagram را بفرستید.\n"
                "پست: https://www.instagram.com/p/SHORTCODE/\n"
                "استوری: https://www.instagram.com/stories/username/123456789/"
            )
            return

        rate = await self._rate_limiter.check(user.id)
        if not rate.allowed:
            await message.reply_text(
                f"⏳ تعداد درخواست‌ها زیاد شده است؛ حدود {rate.retry_after_seconds} ثانیه "
                "بعد دوباره امتحان کنید."
            )
            return

        if not await self._mark_active(user.id):
            await message.reply_text("یک دانلود دیگر برای شما در حال انجام است؛ کمی صبر کنید.")
            return

        item_name = "استوری" if target.is_story else "محتوا"
        status = await message.reply_text(f"⏳ در حال دریافت {item_name} از Instagram…")
        try:
            async with self._download_slots:
                with TemporaryDirectory(prefix="ig-bot-") as temporary_directory:
                    result = await asyncio.to_thread(
                        self._downloader.download,
                        target,
                        Path(temporary_directory),
                    )
                    await status.edit_text("📤 دریافت شد؛ در حال ارسال به Telegram…")
                    await message.get_bot().send_chat_action(
                        chat_id=message.chat_id,
                        action=ChatAction.UPLOAD_VIDEO,
                    )
                    skipped = await self._send_result(message, result)

            if skipped:
                await status.edit_text(
                    f"✅ ارسال کامل شد. {skipped} فایل به‌دلیل محدودیت حجم Telegram ارسال نشد."
                )
            else:
                await status.edit_text("✅ دانلود و ارسال با موفقیت انجام شد.")
        except InstagramDownloadError as exc:
            await status.edit_text(f"❌ {exc}")
        except (TimedOut, NetworkError):
            await status.edit_text(
                "❌ ارتباط با Telegram قطع یا کند شد؛ لطفاً دوباره امتحان کنید."
            )
        except BadRequest as exc:
            LOGGER.warning("Telegram rejected media: %s", exc)
            await status.edit_text(
                "❌ Telegram این فایل را نپذیرفت؛ احتمالاً حجم یا قالب آن پشتیبانی نمی‌شود."
            )
        except TelegramError:
            LOGGER.exception("Telegram API error")
            await status.edit_text("❌ هنگام ارسال فایل خطایی رخ داد؛ دوباره امتحان کنید.")
        except Exception:
            LOGGER.exception("Unexpected handler error")
            await status.edit_text("❌ خطای غیرمنتظره رخ داد؛ لطفاً کمی بعد دوباره امتحان کنید.")
        finally:
            await self._unmark_active(user.id)

    async def _mark_active(self, user_id: int) -> bool:
        async with self._active_users_lock:
            if user_id in self._active_users:
                return False
            self._active_users.add(user_id)
            return True

    async def _unmark_active(self, user_id: int) -> None:
        async with self._active_users_lock:
            self._active_users.discard(user_id)

    async def _send_result(self, message: Message, result: DownloadResult) -> int:
        max_upload_bytes = self._settings.max_upload_mb * 1024 * 1024
        accepted: list[Path] = []
        skipped = 0

        for path in result.media_paths:
            limit = PHOTO_UPLOAD_LIMIT if _is_photo(path) else max_upload_bytes
            if path.stat().st_size > limit:
                skipped += 1
            else:
                accepted.append(path)

        if not accepted:
            raise BadRequest(
                "All downloaded files exceed the configured Telegram upload limit"
            )

        caption = build_caption(result)
        if len(accepted) == 1:
            await self._send_single(message, accepted[0], caption)
            return skipped

        caption_used = False
        for offset in range(0, len(accepted), MEDIA_GROUP_LIMIT):
            batch = accepted[offset : offset + MEDIA_GROUP_LIMIT]
            await self._send_group(
                message,
                batch,
                caption if not caption_used else None,
            )
            caption_used = True
        return skipped

    @staticmethod
    async def _send_single(message: Message, path: Path, caption: str) -> None:
        with path.open("rb") as media:
            if _is_photo(path):
                await message.reply_photo(photo=media, caption=caption)
            else:
                await message.reply_video(
                    video=media,
                    caption=caption,
                    supports_streaming=True,
                )

    @staticmethod
    async def _send_group(
        message: Message,
        paths: list[Path],
        caption: str | None,
    ) -> None:
        handles: list[BinaryIO] = []
        media_group: list[InputMediaPhoto | InputMediaVideo] = []
        try:
            for index, path in enumerate(paths):
                handle = path.open("rb")
                handles.append(handle)
                item_caption = caption if index == 0 else None
                if _is_photo(path):
                    media_group.append(InputMediaPhoto(media=handle, caption=item_caption))
                else:
                    media_group.append(
                        InputMediaVideo(
                            media=handle,
                            caption=item_caption,
                            supports_streaming=True,
                        )
                    )
            await message.reply_media_group(media=media_group)
        finally:
            for handle in handles:
                handle.close()


def _is_photo(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
