from pathlib import Path

import pytest

from ig_telegram_bot.instagram import (
    InvalidInstagramLink,
    _natural_filename_key,
    extract_shortcode,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://www.instagram.com/p/ABC_123-x/", "ABC_123-x"),
        ("بگیر https://instagram.com/reel/C9dEfg12/?igsh=abc", "C9dEfg12"),
        ("https://m.instagram.com/reels/Short_Code-1#fragment", "Short_Code-1"),
        ("https://www.instagram.com/tv/ABCDE12345/", "ABCDE12345"),
    ],
)
def test_extract_shortcode(text: str, expected: str) -> None:
    assert extract_shortcode(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "instagram.com/p/ABCDEF/",
        "https://example.com/p/ABCDEF/",
        "https://www.instagram.com/username/",
        "https://www.instagram.com/stories/user/123/",
        "یک متن معمولی",
    ],
)
def test_rejects_unsupported_links(text: str) -> None:
    with pytest.raises(InvalidInstagramLink):
        extract_shortcode(text)


def test_carousel_filenames_are_sorted_numerically() -> None:
    paths = [Path("post_10.jpg"), Path("post_2.jpg"), Path("post_1.jpg")]

    assert sorted(paths, key=_natural_filename_key) == [
        Path("post_1.jpg"),
        Path("post_2.jpg"),
        Path("post_10.jpg"),
    ]
