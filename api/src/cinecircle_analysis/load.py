"""Write a fake `Dataset` to the LOCAL database, and take it out again (plan P8).

This is the only code in the repository that writes as `postgres` with triggers off, so it refuses
any database that is not on this machine before it opens a connection. The app
(`cinecircle_api`) never imports it.
"""

from collections.abc import Iterable, Iterator
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Connection, Engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert

from cinecircle_analysis.fakedata import FAKE_DOMAIN, FAKE_TMDB_BASE, GENRES, Dataset

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_CHUNK = 2000


class NotLocal(Exception):
    """The database is not on this machine; fake data is never written there."""


def assert_local(engine: Engine) -> None:
    """Raise `NotLocal` unless the engine points at this machine. Reads the URL only: no
    connection is made. A `host=`/`hostaddr=` query option overrides the URL's host in libpq, so
    those count too, and a missing host (a unix socket) is refused as well."""
    url = engine.url
    hosts = [url.host]
    for option in ("host", "hostaddr"):
        value = url.query.get(option)
        if value is not None:
            hosts.extend([value] if isinstance(value, str) else value)
    if not hosts[0] or any(host not in LOCAL_HOSTS for host in hosts if host):
        raise NotLocal(f"refusing to touch {url.host or 'a non-TCP database'}: not a local host")


def _table(name: str, *columns: sa.Column) -> sa.TableClause:
    return sa.table(name, *columns, schema="app")


def _col(name: str, type_: Any = None) -> sa.ColumnClause:
    return sa.column(name, type_) if type_ is not None else sa.column(name)


_GENRES = _table("genres", _col("id"), _col("name_en"), _col("name_he"))
_PROFILES = _table(
    "profiles", _col("id"), _col("username"), _col("display_name"), _col("created_at")
)
_DETAILS = _table("profile_details", _col("user_id"))
_SETTINGS = _table("user_settings", _col("user_id"))
_PREFS = _table("user_genre_prefs", _col("user_id"), _col("genre_id"))
_FOLLOWS = _table(
    "follows",
    _col("follower_id"),
    _col("followee_id"),
    _col("status"),
    _col("created_at"),
    _col("responded_at"),
)
_TITLES = _table(
    "titles",
    _col("id"),
    _col("tmdb_id"),
    _col("media_type"),
    _col("name_en"),
    _col("name_he"),
    _col("year_start"),
    _col("imdb_rating"),
    _col("tmdb_rating"),
    _col("raw_tmdb", JSONB),
)
_TITLE_GENRES = _table("title_genres", _col("title_id"), _col("genre_id"))
_POSTS = _table(
    "posts",
    _col("id"),
    _col("author_id"),
    _col("title_id"),
    _col("season_number"),
    _col("rating"),
    _col("is_shared"),
    _col("created_at"),
    _col("updated_at"),
)
_WISHES = _table(
    "wishlist_items",
    _col("owner_id"),
    _col("title_id"),
    _col("source"),
    _col("source_post_id"),
    _col("status"),
    _col("fit_at_save"),
    _col("added_at"),
    _col("watched_at"),
)
_EVENTS = _table(
    "events",
    _col("user_id"),
    _col("event_type"),
    _col("title_id"),
    _col("post_id"),
    _col("props", JSONB),
    _col("created_at"),
)
_AUTH_USERS = sa.table(
    "users",
    _col("id"),
    _col("email"),
    _col("aud"),
    _col("role"),
    _col("created_at"),
    schema="auth",
)

_WIPE_USERS = sa.text("DELETE FROM auth.users WHERE email LIKE :pattern").bindparams(
    pattern=f"%@{FAKE_DOMAIN}"
)
_WIPE_TITLES = sa.text("DELETE FROM app.titles WHERE tmdb_id >= :base").bindparams(
    base=FAKE_TMDB_BASE
)


def _chunks(rows: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(rows), _CHUNK):
        yield rows[start : start + _CHUNK]


def _insert(conn: Connection, table: sa.TableClause, rows: list[dict[str, Any]]) -> int:
    for chunk in _chunks(rows):
        conn.execute(sa.insert(table), chunk)
    return len(rows)


def _insert_returning(
    conn: Connection, table: sa.TableClause, rows: list[dict[str, Any]], *returning: str
) -> list[Any]:
    """Insert and return the named columns of every row (the database assigns the ids)."""
    out: list[Any] = []
    for chunk in _chunks(rows):
        result = conn.execute(
            sa.insert(table).returning(*(table.c[name] for name in returning)), chunk
        )
        out.extend(result.all())
    return out


def _wipe(conn: Connection) -> None:
    """Fake users (their profiles, follows, posts, wishlist, genre picks, events and
    notifications cascade), then fake titles (their genre links cascade). Genres stay: they are
    shared catalogue rows. Must run with foreign keys active, so not under `replica`."""
    conn.execute(_WIPE_USERS)
    conn.execute(_WIPE_TITLES)


def wipe(engine: Engine) -> None:
    assert_local(engine)
    with engine.begin() as conn:
        _wipe(conn)


def load(engine: Engine, dataset: Dataset) -> dict[str, int]:
    """Replace any fake data with `dataset`, in one transaction as the connecting role. Returns
    the number of rows written per table.

    Inside the transaction `session_replication_role = replica` switches the triggers off, so the
    generated timestamps survive (the `watched_at` trigger would stamp now()) and no follow
    notifications appear. CHECK constraints still apply; foreign keys are then only as good as the
    generator, which the unit tests pin."""
    assert_local(engine)
    with engine.begin() as conn:
        _wipe(conn)
        conn.execute(sa.text("SET LOCAL session_replication_role = replica"))
        return _write(conn, dataset)


def _write(conn: Connection, ds: Dataset) -> dict[str, int]:
    counts: dict[str, int] = {}
    conn.execute(
        pg_insert(_GENRES).on_conflict_do_nothing(index_elements=["id"]),
        [{"id": gid, "name_en": en, "name_he": he} for gid, en, he in GENRES],
    )

    user_ids = {u.n: u.id for u in ds.users}
    _insert(
        conn,
        _AUTH_USERS,
        [
            {
                "id": u.id,
                "email": u.email,
                "aud": "authenticated",
                "role": "authenticated",
                "created_at": u.signed_up,
            }
            for u in ds.users
        ],
    )
    counts["profiles"] = _insert(
        conn,
        _PROFILES,
        [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "created_at": u.signed_up,
            }
            for u in ds.users
        ],
    )
    _insert(conn, _DETAILS, [{"user_id": u.id} for u in ds.users])
    _insert(conn, _SETTINGS, [{"user_id": u.id} for u in ds.users])
    counts["user_genre_prefs"] = _insert(
        conn, _PREFS, [{"user_id": u.id, "genre_id": g} for u in ds.users for g in u.picks]
    )
    counts["follows"] = _insert(
        conn,
        _FOLLOWS,
        [
            {
                "follower_id": user_ids[f.follower],
                "followee_id": user_ids[f.followee],
                "status": f.status,
                "created_at": f.created_at,
                "responded_at": f.responded_at,
            }
            for f in ds.follows
        ],
    )

    title_rows = _insert_returning(
        conn,
        _TITLES,
        [
            {
                "tmdb_id": t.tmdb_id,
                "media_type": t.media_type,
                "name_en": t.name_en,
                "name_he": t.name_he,
                "year_start": t.year,
                "imdb_rating": t.imdb_rating,
                "tmdb_rating": t.tmdb_rating,
                "raw_tmdb": {"fake": True},
            }
            for t in ds.titles
        ],
        "id",
        "tmdb_id",
    )
    by_tmdb = {tmdb_id: row_id for row_id, tmdb_id in title_rows}
    title_ids = {t.i: by_tmdb[t.tmdb_id] for t in ds.titles}
    counts["titles"] = len(title_rows)
    counts["title_genres"] = _insert(
        conn,
        _TITLE_GENRES,
        [{"title_id": title_ids[t.i], "genre_id": g} for t in ds.titles for g in t.genre_ids],
    )

    post_rows = _insert_returning(
        conn,
        _POSTS,
        [
            {
                "author_id": user_ids[p.author],
                "title_id": title_ids[p.title],
                "season_number": 0,
                "rating": p.rating,
                "is_shared": p.is_shared,
                "created_at": p.created_at,
                "updated_at": p.created_at,
            }
            for p in ds.posts
        ],
        "id",
        "author_id",
        "title_id",
    )
    ids_by_uuid = {(author, title): row_id for row_id, author, title in post_rows}
    post_ids = {
        (p.author, p.title): ids_by_uuid[(user_ids[p.author], title_ids[p.title])] for p in ds.posts
    }
    counts["posts"] = len(post_rows)

    counts["wishlist_items"] = _insert(
        conn,
        _WISHES,
        [
            {
                "owner_id": user_ids[w.owner],
                "title_id": title_ids[w.title],
                "source": w.source,
                "source_post_id": post_ids[w.source_post] if w.source_post else None,
                "status": w.status,
                "fit_at_save": w.fit_at_save,
                "added_at": w.added_at,
                "watched_at": w.watched_at,
            }
            for w in ds.wishes
        ],
    )
    counts["events"] = _insert(
        conn,
        _EVENTS,
        [
            {
                "user_id": user_ids[e.user],
                "event_type": e.event_type,
                "title_id": title_ids[e.title] if e.title is not None else None,
                "post_id": post_ids[e.post] if e.post is not None else None,
                "props": e.props,
                "created_at": e.created_at,
            }
            for e in ds.events
        ],
    )
    return counts


def count_rows(counts: Iterable[tuple[str, int]]) -> str:
    """The counts as aligned lines, for the CLI."""
    pairs = list(counts)
    width = max((len(name) for name, _ in pairs), default=0)
    return "\n".join(f"  {name:<{width}}  {n:>6}" for name, n in pairs)
