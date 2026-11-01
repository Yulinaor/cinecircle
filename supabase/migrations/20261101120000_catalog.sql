-- Phase 1: catalogue tables (external TMDB/OMDb data, cached). DDL copied verbatim from spec 02 §6.
-- Writes go through the API's service connection only; signed-in users may read; anon gets nothing.

CREATE TABLE app.titles (
    id            BIGSERIAL PRIMARY KEY,
    tmdb_id       INTEGER NOT NULL,
    media_type    TEXT NOT NULL CHECK (media_type IN ('movie','series')),
    imdb_id       TEXT UNIQUE,
    name_en       TEXT NOT NULL,
    name_he       TEXT,
    overview_en   TEXT,
    overview_he   TEXT,
    year_start    SMALLINT,
    year_end      SMALLINT,
    runtime_min   INTEGER,
    season_count  SMALLINT,
    poster_path   TEXT,
    imdb_rating   NUMERIC(3,1),
    imdb_votes    INTEGER,
    rt_score      SMALLINT,           -- Rotten Tomatoes %
    metacritic    SMALLINT,
    tmdb_rating   NUMERIC(3,1),
    raw_tmdb      JSONB NOT NULL,
    raw_omdb      JSONB,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tmdb_id, media_type)
);
CREATE TABLE app.title_seasons (
    title_id      BIGINT REFERENCES app.titles(id) ON DELETE CASCADE,
    season_number SMALLINT CHECK (season_number >= 1),
    name_en TEXT, name_he TEXT, overview_en TEXT, overview_he TEXT,
    poster_path TEXT, air_date DATE, episode_count SMALLINT,
    PRIMARY KEY (title_id, season_number)
);
CREATE TABLE app.genres (id INTEGER PRIMARY KEY, name_en TEXT NOT NULL, name_he TEXT); -- TMDB genre ids
CREATE TABLE app.title_genres (
    title_id BIGINT REFERENCES app.titles(id) ON DELETE CASCADE,
    genre_id INTEGER REFERENCES app.genres(id),
    PRIMARY KEY (title_id, genre_id)
);

ALTER TABLE app.titles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.title_seasons ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.genres        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.title_genres  ENABLE ROW LEVEL SECURITY;

CREATE POLICY catalog_read ON app.titles        FOR SELECT TO authenticated USING (true);
CREATE POLICY catalog_read ON app.title_seasons FOR SELECT TO authenticated USING (true);
CREATE POLICY catalog_read ON app.genres        FOR SELECT TO authenticated USING (true);
CREATE POLICY catalog_read ON app.title_genres  FOR SELECT TO authenticated USING (true);

-- Start from nothing, then grant exactly: read for authenticated, everything for service_role.
REVOKE ALL ON app.titles, app.title_seasons, app.genres, app.title_genres
    FROM PUBLIC, anon, authenticated;
GRANT SELECT ON app.titles, app.title_seasons, app.genres, app.title_genres TO authenticated;
GRANT ALL ON app.titles, app.title_seasons, app.genres, app.title_genres TO service_role;
GRANT USAGE, SELECT ON SEQUENCE app.titles_id_seq TO service_role;
