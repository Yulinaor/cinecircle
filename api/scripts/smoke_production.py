"""Smoke test of the deployed CineCircle: is it up, closed to strangers and free of secrets?

Read-only: a handful of GET and OPTIONS requests, no sign-in, no key of any kind. Not imported by
the app. Exit code 0 when every check passes, 1 otherwise.

    npm run smoke:prod
    uv --directory api run python scripts/smoke_production.py --api https://... --web https://...

The free Render service sleeps and takes up to a minute to wake, so `/live` is retried first.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

DEFAULT_API = "https://cinecircle-server.onrender.com"
DEFAULT_WEB = "https://cinecircle-web.onrender.com"
WAKE_SECONDS = 90  # how long to wait for a sleeping server, by the clock
WAKE_INTERVAL = 5
LIVE_TIMEOUT = 10  # one attempt at /live; the client's own 30 s would make the deadline a guess
OTHER_ORIGIN = "https://example.com"
MAX_BUNDLE_FILES = 60

_SCRIPT_SRC = re.compile(r"""<(?:script|link)\b[^>]*?\b(?:src|href)=["']([^"']+\.js)["']""")
# Chunks a bundle loads: `import("./x.js")` (relative to the file) and Vite's "assets/x.js" list.
_CHUNK_REF = re.compile(r"""["']((?:\./|/?assets/)[\w.\-]+\.js)["']""")
# Only the publishable key may ship in the web bundle. The bare words "sb_secret_" and
# "service_role" appear in supabase-js itself, so look for key-shaped values instead.
_SECRET_KEY = re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}")
_JWT = re.compile(r"eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+")


@dataclass(frozen=True)
class Failure:
    check: str
    detail: str


Log = Callable[[str, "Failure | None"], None]


def _is_html(response: httpx.Response) -> bool:
    return response.status_code == 200 and "text/html" in response.headers.get("content-type", "")


def _wake(
    client: httpx.Client,
    api: str,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> str | None:
    """Poll `/live` until it answers 200, for at most WAKE_SECONDS by the clock. None on success,
    else what the last attempt showed. Each attempt has its own short timeout, so a server that
    accepts the connection and then says nothing cannot hold the script past the deadline."""
    deadline = clock() + WAKE_SECONDS
    problem = "no attempt made"
    while True:
        timeout = max(1.0, min(LIVE_TIMEOUT, deadline - clock()))
        try:
            response = client.get(f"{api}/live", timeout=timeout)
        except httpx.HTTPError as error:
            problem = f"no answer ({type(error).__name__})"
        else:
            if response.status_code == 200:
                return None
            problem = f"status {response.status_code}"
        remaining = deadline - clock()
        if remaining <= 0:
            return f"{problem} after {WAKE_SECONDS} s"
        sleep(min(WAKE_INTERVAL, remaining))


def _chunk_url(web: str, referrer: str, ref: str) -> str:
    base = f"{web}/" if ref.lstrip("/").startswith("assets/") else referrer
    return urljoin(base, ref)


def _bundle_files(
    client: httpx.Client, web: str, index: httpx.Response
) -> tuple[dict[str, str], str | None]:
    """The scripts the page loads, and the chunks those import, as url -> text, plus what stopped
    the scan from being complete (None when it was). A scan that skipped something must not pass."""
    files: dict[str, str] = {f"{web}/": index.text}
    listed = [urljoin(f"{web}/", src) for src in _SCRIPT_SRC.findall(index.text)]
    if not listed:
        return files, "no script found in the page, so there was nothing to scan"
    queue = list(listed)
    host = urlparse(web).netloc
    while queue:
        url = queue.pop(0)
        if url in files or urlparse(url).netloc != host:
            continue
        if len(files) > MAX_BUNDLE_FILES:
            return files, f"more than {MAX_BUNDLE_FILES} files; stopped at the limit"
        response = client.get(url, follow_redirects=True)
        if response.status_code != 200:
            if url not in listed and response.status_code == 404:
                continue  # a guessed chunk name that does not exist is not a failure
            # Anything else (a 429, a 5xx, a listed script that is gone) leaves the scan incomplete.
            return files, f"{urlparse(url).path} answered {response.status_code}"
        files[url] = response.text
        queue.extend(_chunk_url(web, url, ref) for ref in _CHUNK_REF.findall(response.text))
    return files, None


def _secret_in(text: str) -> str | None:
    """The kind of server-side key `text` holds, or None. Never returns the key itself."""
    if _SECRET_KEY.search(text):
        return "sb_secret_"
    for match in _JWT.finditer(text):
        payload = match.group().split(".")[1]
        try:
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except ValueError:  # not base64, not UTF-8, not JSON: just something shaped like a token
            continue
        if isinstance(claims, dict) and claims.get("role") == "service_role":
            return "service_role"
    return None


def check(
    client: httpx.Client,
    api_url: str,
    web_url: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    log: Log | None = None,
) -> list[Failure]:
    """Run every check against the two deployments through `client`. Returns the failures (empty
    when all is well). `log(name, failure_or_None)` is told about each check as it finishes."""
    api, web = api_url.rstrip("/"), web_url.rstrip("/")
    failures: list[Failure] = []

    def run(name: str, test: Callable[[], str | None]) -> bool:
        try:
            detail = test()
        except httpx.HTTPError as error:
            detail = f"request failed ({type(error).__name__})"
        failure = Failure(name, detail) if detail else None
        if failure:
            failures.append(failure)
        if log:
            log(name, failure)
        return failure is None

    def status_is(path: str, expected: int) -> Callable[[], str | None]:
        def test() -> str | None:
            got = client.get(f"{api}{path}").status_code
            return None if got == expected else f"expected {expected}, got {got}"

        return test

    if not run("GET /live is 200", lambda: _wake(client, api, sleep, clock)):
        return failures  # nothing else can answer; the rest would only repeat the same news

    def health() -> str | None:
        response = client.get(f"{api}/health")
        try:
            body = response.json()
        except ValueError:
            return f"status {response.status_code}, body is not JSON"
        if not isinstance(body, dict):
            return f"status {response.status_code}, body is not a JSON object"
        if response.status_code == 200 and body.get("db") == "ok":
            return None
        return f"status {response.status_code}, db {body.get('db')!r}"

    run("GET /health is ok", health)
    run("GET /docs is 404", status_is("/docs", 404))
    run("GET /openapi.json is 404", status_is("/openapi.json", 404))
    run("GET /me without a token is 401", status_is("/me", 401))

    def preflight(origin: str) -> httpx.Response:
        return client.request(
            "OPTIONS",
            f"{api}/me",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

    def allows_web() -> str | None:
        response = preflight(web)
        allowed = response.headers.get("access-control-allow-origin")
        if response.status_code == 200 and allowed in (web, "*"):
            return None
        return f"status {response.status_code}, allow-origin {allowed!r}"

    def refuses_other() -> str | None:
        allowed = preflight(OTHER_ORIGIN).headers.get("access-control-allow-origin")
        return None if allowed is None else f"allow-origin {allowed!r} for {OTHER_ORIGIN}"

    run("OPTIONS /me allows the web origin", allows_web)
    run("OPTIONS /me refuses another origin", refuses_other)

    index: list[httpx.Response] = []

    def serves(path: str) -> Callable[[], str | None]:
        def test() -> str | None:
            response = client.get(f"{web}{path}", follow_redirects=True)
            if path == "/":
                index.append(response)
            if _is_html(response):
                return None
            return f"status {response.status_code}, {response.headers.get('content-type')!r}"

        return test

    run("web / serves the app", serves("/"))
    run("web /stats serves the app", serves("/stats"))

    def no_secret() -> str | None:
        if not index or not _is_html(index[0]):
            return "the page did not load, so the bundle was not checked"
        files, problem = _bundle_files(client, web, index[0])
        for url, text in files.items():
            kind = _secret_in(text)
            if kind:
                # Name the file and the kind only, never the text around it.
                return f"a {kind} key was found in {urlparse(url).path}"
        return problem

    run("web bundle holds no secret key", no_secret)
    return failures


def _make_client() -> httpx.Client:
    # No redirects by default: a redirect on the API would hide what the API itself answered.
    return httpx.Client(timeout=30, follow_redirects=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--web", default=DEFAULT_WEB, help="web base URL")
    args = parser.parse_args(argv)

    def log(name: str, failure: Failure | None) -> None:
        print(f"  ok    {name}" if failure is None else f"  FAIL  {name}: {failure.detail}")

    print(f"api {args.api}\nweb {args.web}")
    with _make_client() as client:
        failures = check(client, args.api, args.web, log=log)
    print(f"{len(failures)} check(s) failed" if failures else "all checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
