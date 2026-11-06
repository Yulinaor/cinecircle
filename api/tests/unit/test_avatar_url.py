"""Only Google user-content avatars are stored: user_metadata is user-writable."""

import pytest

from cinecircle_api.routes.me import safe_avatar_url

BACKSLASH = chr(92)


@pytest.mark.parametrize(
    "url",
    [
        "https://lh3.googleusercontent.com/a/abc=s96-c",
        "https://lh4.googleusercontent.com/a.png",
        "https://x.y.googleusercontent.com/a.png",
    ],
)
def test_google_user_content_hosts_accepted(url):
    assert safe_avatar_url(url) == url


@pytest.mark.parametrize(
    "value",
    [
        "https://lh3.example.com/a.png",
        "https://evil.com/x.googleusercontent.com",
        "https://googleusercontent.com.evil.com/a.png",
        "https://evilgoogleusercontent.com/a.png",
        "https://user@evil.com/lh3.googleusercontent.com",
        "http://lh3.googleusercontent.com/a.png",
        "//lh3.googleusercontent.com/a.png",
        "https:///a.png",
        # Browsers read a backslash as "/" (WHATWG) while urlsplit keeps it in the host.
        f"https://evil.com{BACKSLASH}.googleusercontent.com/a.png",
        f"https://evil.com{BACKSLASH}@lh3.googleusercontent.com/a.png",
        f"https://lh3.googleusercontent.com{BACKSLASH}a.png",
        "https://evil.com%5C.googleusercontent.com/a.png",
        "https://evil.com%5c.googleusercontent.com/a.png",
        "https://lh3.googleusercontent.com:8443/a.png",
        "https://lh3.googleusercontent.com:443/a.png",
        "https://lh3.googleusercontent.com:/a.png",
        "https://lh3.googleusercontent.com/a b.png",
        "https://lh3.googleusercontent.com/a.png\n",
        "https://lh3.google\tusercontent.com/a.png",
        "https://evil.com\t.googleusercontent.com/a.png",
        " https://lh3.googleusercontent.com/a.png",
        "https://lh3.googleusercontent.com/a.png\x00",
        "https://lh3.googleusercontent.com/a.png\x7f",
        "https://lѕ.googleusercontent.com/a.png",
        "not a url",
        "",
        5,
        None,
        {"x": 1},
    ],
)
def test_everything_else_is_dropped(value):
    assert safe_avatar_url(value) is None


def test_overlong_url_dropped():
    prefix = "https://lh3.googleusercontent.com/"
    assert safe_avatar_url(prefix + "a" * (512 - len(prefix))) is not None
    assert safe_avatar_url(prefix + "a" * (513 - len(prefix))) is None
