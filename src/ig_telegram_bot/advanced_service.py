from __future__ import annotations

import logging
from pathlib import Path

from telegram import Message
from telegram.error import BadRequest

from .instagram import DownloadResult
from .service import (
    MEDIA_GROUP_LIMIT,
    PHOTO_UPLOAD_LIMIT,
    InstagramBotService,
    _is_photo,
    build_caption,
)

LOGGER = logging.getLogger(__name__)


class AdvancedInstagramBotService(InstagramBotService):
    """Production delivery improvements without changing download semantics."""

    async def _send_result(self, message: Message, result: DownloadResult) -> int:
        max_upload_bytes = self._settings.max_upload_mb * 1024 * 1024
        groupable: list[Path] = []
        documents: list[Path] = []
        skipped = 0

        for path in result.media_paths:
            size = path.stat().st_size
            if size > max_upload_bytes:
                skipped += 1
            elif _is_photo(path) and size > PHOTO_UPLOAD_LIMIT:
                documents.append(path)
            else:
                groupable.append(path)

        if not groupable and not documents:
            raise BadRequest("All downloaded files exceed the configured Telegram upload limit")

        caption = build_caption(result)
        caption_used = False
        sent = 0

        for offset in range(0, len(groupable), MEDIA_GROUP_LIMIT):
            batch = groupable[offset : offset + MEDIA_GROUP_LIMIT]
            batch_caption = caption if not caption_used else None
            batch_sent, batch_skipped = await self._send_batch_resilient(
                message,
                batch,
                batch_caption,
            )
            sent += batch_sent
            skipped += batch_skipped
            if batch_sent and batch_caption:
                caption_used = True

        for path in documents:
            item_caption = caption if not caption_used else None
            if await self._try_send_document(message, path, item_caption):
                sent += 1
                caption_used = True
            else:
                skipped += 1

        if sent == 0:
            raise BadRequest("Telegram rejected every downloaded media file")
        return skipped

    async def _send_batch_resilient(
        self,
        message: Message,
        paths: list[Path],
        caption: str | None,
    ) -> tuple[int, int]:
        if not paths:
            return 0, 0

        if len(paths) >= 2:
            try:
                await self._send_group(message, paths, caption)
                return len(paths), 0
            except BadRequest as exc:
                LOGGER.warning(
                    "Media group rejected; falling back to individual sends: %s",
                    exc,
                )

        sent = 0
        skipped = 0
        pending_caption = caption
        for path in paths:
            delivered = await self._send_single_with_fallback(
                message,
                path,
                pending_caption,
            )
            if delivered:
                sent += 1
                pending_caption = None
            else:
                skipped += 1
        return sent, skipped

    async def _send_single_with_fallback(
        self,
        message: Message,
        path: Path,
        caption: str | None,
    ) -> bool:
        try:
            await self._send_single(message, path, caption or "")
            return True
        except BadRequest as exc:
            LOGGER.warning(
                "Media %s rejected; trying as document: %s",
                path.name,
                exc,
            )
            return await self._try_send_document(message, path, caption)

    @staticmethod
    async def _try_send_document(
        message: Message,
        path: Path,
        caption: str | None,
    ) -> bool:
        try:
            with path.open("rb") as media:
                await message.reply_document(document=media, caption=caption)
            return True
        except BadRequest as exc:
            LOGGER.warning("Document %s rejected by Telegram: %s", path.name, exc)
            return False
