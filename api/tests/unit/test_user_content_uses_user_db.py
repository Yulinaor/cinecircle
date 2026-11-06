"""User content must go through the per-request UserDb (RLS as the caller), never the raw engine.

The engine connects as a role that bypasses RLS. Only the shared catalogue (TitleService) and the
health probe may use it.
"""

from pathlib import Path

import cinecircle_api

PACKAGE = Path(cinecircle_api.__file__).parent
FORBIDDEN = ("app.state.engine", "state.engine", "get_engine")


def _user_content_modules() -> list[Path]:
    modules = [
        p
        for folder in ("people", "follows", "notifications")
        for p in (PACKAGE / folder).glob("**/*.py")
    ]
    modules += [
        PACKAGE / "routes" / f"{name}.py" for name in ("me", "users", "follows", "notifications")
    ]
    return modules


def test_guard_covers_the_user_content_modules():
    names = {p.relative_to(PACKAGE).as_posix() for p in _user_content_modules()}
    assert {
        "people/repository.py",
        "follows/repository.py",
        "notifications/repository.py",
        "routes/me.py",
        "routes/users.py",
        "routes/follows.py",
        "routes/notifications.py",
    } <= names


def test_user_content_modules_never_touch_the_engine():
    offenders = [
        f"{path.relative_to(PACKAGE).as_posix()}: {word}"
        for path in _user_content_modules()
        for word in FORBIDDEN
        if word in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
