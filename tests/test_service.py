from pathlib import Path

from ig_telegram_bot.instagram import DownloadResult
from ig_telegram_bot.service import build_caption


def test_caption_has_owner_and_stays_within_telegram_limit() -> None:
    result = DownloadResult(
        shortcode="ABCDEF",
        source_url="https://www.instagram.com/p/ABCDEF/",
        owner_username="example_user",
        caption="الف" * 2000,
        media_paths=(Path("example.jpg"),),
    )

    caption = build_caption(result)

    assert "@example_user" in caption
    assert len(caption) <= 1000
    assert caption.endswith("…")
