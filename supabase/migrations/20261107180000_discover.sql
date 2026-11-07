-- Phase 6: Discover (plan P3, P7). Two catalogue-style tables, DDL verbatim from
-- docs/spec/02 section 6, plus the marker that says when a title's reviews were last fetched.
-- Both are written by the API's service session only (TMDB data, never user content).

ALTER TABLE app.titles ADD COLUMN reviews_fetched_at TIMESTAMPTZ;  -- NULL = never fetched

CREATE TABLE app.external_reviews (
    id               BIGSERIAL PRIMARY KEY,
    title_id         BIGINT NOT NULL REFERENCES app.titles(id) ON DELETE CASCADE,
    source           TEXT NOT NULL DEFAULT 'tmdb',
    source_review_id TEXT NOT NULL,
    author_name      TEXT NOT NULL,         -- shown as "Review by <author> on TMDB"
    excerpt          TEXT NOT NULL CHECK (char_length(excerpt) <= 300),
    url              TEXT NOT NULL,
    author_rating    NUMERIC(3,1),
    language         TEXT,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_review_id)
);
CREATE INDEX external_reviews_title_idx ON app.external_reviews (title_id);

CREATE TABLE app.discover_cache (
    list_key   TEXT,                       -- 'trending:movie:week', 'recs:movie:603'
    locale     TEXT,
    payload    JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (list_key, locale)
);

ALTER TABLE app.external_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.discover_cache   ENABLE ROW LEVEL SECURITY;

-- Reviews are public catalogue data, like titles: any signed-in user may read them.
CREATE POLICY catalog_read ON app.external_reviews FOR SELECT TO authenticated USING (true);
-- discover_cache has no policy and no grant for users: only the service session reads it.

-- Start from nothing, then grant exactly (same pattern as the catalogue tables).
REVOKE ALL ON app.external_reviews, app.discover_cache FROM PUBLIC, anon, authenticated;
GRANT SELECT ON app.external_reviews TO authenticated;
GRANT ALL ON app.external_reviews, app.discover_cache TO service_role;
GRANT USAGE, SELECT ON SEQUENCE app.external_reviews_id_seq TO service_role;
