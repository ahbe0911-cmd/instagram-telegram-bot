from pathlib import Path

import pytest

from ig_telegram_bot.instagram import (
    InstagramDownloader,
    InstagramDownloadError,
    InvalidInstagramLink,
    StorySession,
    _natural_filename_key,
    extract_shortcode,
    parse_instagram_target,
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


def test_parse_story_link() -> None:
    target = parse_instagram_target(
        "بگیر https://www.instagram.com/stories/example.user/12345678901234567/?igsh=abc"
    )

    assert target.is_story is True
    assert target.username == "example.user"
    assert target.media_id == 12345678901234567


def test_extract_shortcode_rejects_story_link() -> None:
    with pytest.raises(InvalidInstagramLink):
        extract_shortcode("https://www.instagram.com/stories/example/123456789/")


@pytest.mark.parametrize(
    "text",
    [
        "instagram.com/p/ABCDEF/",
        "https://example.com/p/ABCDEF/",
        "https://www.instagram.com/username/",
        "یک متن معمولی",
    ],
)
def test_rejects_unsupported_links(text: str) -> None:
    with pytest.raises(InvalidInstagramLink):
        parse_instagram_target(text)


def test_story_requires_server_session_before_network(tmp_path: Path) -> None:
    downloader = InstagramDownloader(
        StorySession(username="", sessionid="", csrftoken="")
    )
    target = parse_instagram_target(
        "https://www.instagram.com/stories/example/123456789/"
    )

    with pytest.raises(InstagramDownloadError, match="سشن Instagram"):
        downloader.download(target, tmp_path)


def test_story_session_cookie_mapping() -> None:
    session = StorySession(
        username="owner",
        sessionid="session-value",
        csrftoken="csrf-value",
        ds_user_id="1234",
    )

    assert session.configured is True
    assert session.cookies() == {
        "sessionid": "session-value",
        "csrftoken": "csrf-value",
        "ds_user_id": "1234",
    }


def test_carousel_filenames_are_sorted_numerically() -> None:
    paths = [Path("post_10.jpg"), Path("post_2.jpg"), Path("post_1.jpg")]

    assert sorted(paths, key=_natural_filename_key) == [
        Path("post_1.jpg"),
        Path("post_2.jpg"),
        Path("post_10.jpg"),
    ]
