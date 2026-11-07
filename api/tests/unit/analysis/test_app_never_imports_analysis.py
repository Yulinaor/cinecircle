"""Plan P6: the loader writes as postgres, so the app must never import it."""

from pathlib import Path

APP = Path(__file__).resolve().parents[3] / "src" / "cinecircle_api"


def test_app_never_imports_analysis():
    files = list(APP.rglob("*.py"))
    assert files, APP
    offenders = [f for f in files if "cinecircle_analysis" in f.read_text(encoding="utf-8")]
    assert offenders == []
