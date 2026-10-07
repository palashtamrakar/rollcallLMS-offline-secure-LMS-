import pytest
from backend.app.youtube import extract_youtube_id


@pytest.mark.parametrize(
    "url, expected_id",
    [
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("  dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
        ("https://youtu.be/abcdefghijk", "abcdefghijk"),
    ],
)
def test_extract_youtube_id_valid(url: str, expected_id: str):
    assert extract_youtube_id(url) == expected_id


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        "not_a_url",
        "https://vimeo.com/12345678",
        "https://youtube.com",
        "https://youtube.com/watch",
        "dQw4w9WgXc",  # 10 chars, too short
        "dQw4w9WgXcQ12",  # 13 chars, too long
    ],
)
def test_extract_youtube_id_invalid(invalid_input: str):
    assert extract_youtube_id(invalid_input) is None
