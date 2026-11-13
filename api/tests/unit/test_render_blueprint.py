"""Static checks on render.yaml (plain text; PyYAML is not a dependency)."""

import re
from pathlib import Path

BLUEPRINT = Path(__file__).resolve().parents[3] / "render.yaml"

API_URL = "https://cinecircle-server-kb2r.onrender.com"
WEB_URL = "https://cinecircle-web.onrender.com"
SECRET_KEYS = ("DATABASE_URL", "TMDB_API_KEY", "OMDB_API_KEY")
# The only env vars that may carry a literal `value:`; anything new (a secret) must fail here.
VALUE_ALLOWLIST = {
    "APP_ENV",
    "CORS_ORIGINS",
    "SUPABASE_URL",
    "PYTHON_VERSION",
    "UV_PYTHON_DOWNLOADS",
    "NODE_VERSION",
    "VITE_API_URL",
    "VITE_SUPABASE_URL",
    "VITE_SUPABASE_PUBLISHABLE_KEY",
}


def _text() -> str:
    return BLUEPRINT.read_text(encoding="utf-8")


def _env_block(key: str) -> str:
    """The lines of one `- key: NAME` env var entry, up to the next entry or a dedent."""
    lines = _text().splitlines()
    start = next(i for i, line in enumerate(lines) if re.fullmatch(rf"\s*- key: {key}", line))
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        block.append(line)
    return "\n".join(block)


def _value(key: str) -> str:
    match = re.search(r"^\s*value: (.+?)\s*$", _env_block(key), re.MULTILINE)
    assert match, f"{key} has no value"
    return match.group(1).strip("'\"")


def test_blueprint_keeps_secrets_out():
    for key in SECRET_KEYS:
        block = _env_block(key)
        assert "sync: false" in block, key
        assert "value:" not in block, key
    text = _text()
    for forbidden in ("sb_secret_", "service_role", "SUPABASE_JWT_SECRET"):
        assert forbidden not in text, forbidden
    assert "postgres://" not in text
    assert "postgresql://" not in text
    assert "eyJ" not in text  # a JWT (service-role or anon key) would start like this


def test_only_allowlisted_env_vars_carry_a_value():
    text = _text()
    keys = re.findall(r"^\s*- key: (\w+)\s*$", text, re.MULTILINE)
    assert set(SECRET_KEYS) <= set(keys)
    for key in keys:
        if "value:" in _env_block(key):
            assert key in VALUE_ALLOWLIST, f"{key} has a literal value"


def test_publishable_key_is_the_publishable_one():
    assert _value("VITE_SUPABASE_PUBLISHABLE_KEY").startswith("sb_publishable_")


def test_blueprint_is_production():
    text = _text()
    assert "APP_ENV" in text
    assert _value("APP_ENV") == "production"
    assert "healthCheckPath: /live" in text
    assert "--factory" in text
    assert "$PORT" in text
    assert "--no-dev" in text
    assert "rm -rf src/cinecircle_analysis" in text


def test_blueprint_rewrites_to_the_app():
    text = _text()
    assert "type: rewrite" in text
    assert "source: /*" in text
    assert "destination: /index.html" in text


def test_blueprint_points_web_at_the_api():
    assert _value("VITE_API_URL") == API_URL
    assert _value("CORS_ORIGINS") == WEB_URL
    for key in ("VITE_API_URL", "CORS_ORIGINS"):
        assert not _value(key).endswith("/")


def test_blueprint_pins_the_tested_setup():
    text = _text()
    assert "rootDir: api" in text
    assert ".venv/bin/uvicorn" in text
    assert "staticPublishPath: web/dist" in text
    assert _value("PYTHON_VERSION") == "3.14.6"
    assert _value("NODE_VERSION") == "22"
    # A Python mismatch must fail the build, not download an interpreter missing at runtime.
    assert _value("UV_PYTHON_DOWNLOADS") == "never"
