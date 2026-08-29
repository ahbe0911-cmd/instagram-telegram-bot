import json
from pathlib import Path
from urllib.request import Request

import pytest

from ig_telegram_bot import instagram as instagram_module
from ig_telegram_bot.instagram import (
    InstagramDownloader,
    InstagramDownloadError,
    InvalidInstagramLink,
    StorySession,
    _natural_filename_key,
    _select_soclip_media,
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


def test_story_requires_provider_before_network(tmp_path: Path) -> None:
    downloader = InstagramDownloader(
        StorySession(username="", sessionid="", csrftoken="")
    )
    target = parse_instagram_target(
        "https://www.instagram.com/stories/example/123456789/"
    )

    with pytest.raises(InstagramDownloadError, match="SOCLIP_API_KEY"):
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


def test_soclip_selects_highest_resolution_video() -> None:
    selected = _select_soclip_media(
        [
            {
                "ext": "mp4",
                "width": 720,
                "height": 1280,
                "url": "https://cdn.example/720.mp4",
            },
            {
                "ext": "jpg",
                "width": 1080,
                "height": 1920,
                "url": "https://cdn.example/thumb.jpg",
            },
            {
                "ext": "mp4",
                "width": 1080,
                "height": 1920,
                "url": "https://cdn.example/1080.mp4",
            },
        ]
    )

    assert selected["url"] == "https://cdn.example/1080.mp4"


class _FakeResponse:
    def __init__(self, body: bytes, url: str, content_length: int | None = None) -> None:
        self._body = body
        self._offset = 0
        self._url = url
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self._url


def test_story_uses_hosted_api_without_instagram_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    api_payload = json.dumps(
        {
            "success": True,
            "data": {
                "source": "instagram",
                "medias": [
                    {
                        "ext": "mp4",
                        "width": 1080,
                        "height": 1920,
                        "url": "https://cdn.example/story.mp4",
                    }
                ],
            },
        }
    ).encode()
    media_bytes = b"fake-video"
    responses = [
        _FakeResponse(api_payload, "https://api.soclip.dev/v1/media"),
        _FakeResponse(
            media_bytes,
            "https://cdn.example/story.mp4",
            content_length=len(media_bytes),
        ),
    ]
    requests: list[Request] = []

    def fake_urlopen(request: Request, timeout: int) -> _FakeResponse:
        del timeout
        requests.append(request)
        return responses.pop(0)

    monkeypatch.setattr(instagram_module, "urlopen", fake_urlopen)

    downloader = InstagramDownloader(
        story_session=StorySession(username="", sessionid="", csrftoken=""),
        soclip_api_key="sc_live_test",
    )
    target = parse_instagram_target(
        "https://www.instagram.com/stories/example/123456789/"
    )
    result = downloader.download(target, tmp_path)

    assert result.owner_username == "example"
    assert len(result.media_paths) == 1
    assert result.media_paths[0].read_bytes() == media_bytes
    assert requests[0].full_url == "https://api.soclip.dev/v1/media"
    assert requests[0].get_header("Authorization") == "Bearer sc_live_test"


def test_carousel_filenames_are_sorted_numerically() -> None:
    paths = [Path("post_10.jpg"), Path("post_2.jpg"), Path("post_1.jpg")]

    assert sorted(paths, key=_natural_filename_key) == [
        Path("post_1.jpg"),
        Path("post_2.jpg"),
        Path("post_10.jpg"),
    ]
