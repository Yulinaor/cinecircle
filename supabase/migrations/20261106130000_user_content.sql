-- Phase 2: user content (posts, wishlist, genre prefs, events). DDL copied verbatim from spec 02 §6.
-- RLS enforces rule 00 R5: an owner sees everything of theirs, an approved follower sees SHARED
-- posts only, everyone else sees none of it. Column-level GRANTs (plan P6) limit what a user may write.

-- ===== Tables (verbatim from spec 02 §6) =========================================================

CREATE TABLE app.posts (
    id                BIGSERIAL PRIMARY KEY,
    author_id         UUID NOT NULL REFERENCES app.profiles(id) ON DELETE CASCADE,
    title_id          BIGINT NOT NULL REFERENCES app.titles(id),
    season_number     SMALLINT NOT NULL DEFAULT 0,      -- 0 = whole movie / whole series
    rating            NUMERIC(3,1) NOT NULL
                      CHECK (rating BETWEEN 1 AND 10 AND rating * 2 = round(rating * 2)),  -- ½ steps
    opinion           TEXT CHECK (char_length(opinion) <= 500),
    contains_spoilers BOOLEAN NOT NULL DEFAULT false,
    is_shared         BOOLEAN NOT NULL DEFAULT true,    -- false = private rating (owner only)
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (author_id, title_id, season_number)
);
-- app check (in a trigger): season_number > 0 only for series and must exist in title_seasons
CREATE INDEX posts_feed_idx ON app.posts (author_id, created_at DESC) WHERE is_shared;

CREATE TABLE app.wishlist_items (
    owner_id       UUID NOT NULL REFERENCES app.profiles(id) ON DELETE CASCADE,
    title_id       BIGINT NOT NULL REFERENCES app.titles(id),
    source         TEXT NOT NULL CHECK (source IN ('post','discover','search')),
    source_post_id BIGINT REFERENCES app.posts(id) ON DELETE SET NULL,
    status         TEXT NOT NULL DEFAULT 'want' CHECK (status IN ('want','watched','dropped')),
    fit_at_save    SMALLINT,                 -- Taste Match % when saved (for evaluation)
    added_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    watched_at     TIMESTAMPTZ,
    PRIMARY KEY (owner_id, title_id)
);

CREATE TABLE app.user_genre_prefs (
    user_id  UUID REFERENCES app.profiles(id) ON DELETE CASCADE,
    genre_id INTEGER REFERENCES app.genres(id),
    PRIMARY KEY (user_id, genre_id)
);

CREATE TABLE app.events (                    -- append-only analytics log, owner-only rows
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID REFERENCES app.profiles(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,   -- post_created, post_viewed, saved, watched, follow_requested, discover_opened, ...
    title_id   BIGINT,
    post_id    BIGINT,
    props      JSONB,           -- e.g. {"fit": 87, "surface": "home"}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===== Row-level security ========================================================================

ALTER TABLE app.posts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.wishlist_items   ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.user_genre_prefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.events           ENABLE ROW LEVEL SECURITY;

-- posts: owner sees all of theirs; approved followers see SHARED posts only
CREATE POLICY posts_read ON app.posts FOR SELECT TO authenticated
  USING (author_id = auth.uid() OR (is_shared AND app.follows_approved(author_id)));
CREATE POLICY posts_write ON app.posts FOR ALL TO authenticated
  USING (author_id = auth.uid()) WITH CHECK (author_id = auth.uid());

-- wishlist, genre prefs, events: owner only
CREATE POLICY wishlist_owner ON app.wishlist_items FOR ALL TO authenticated
  USING (owner_id = auth.uid()) WITH CHECK (owner_id = auth.uid());
CREATE POLICY prefs_owner ON app.user_genre_prefs FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
-- events are append-only: a read policy and an insert policy, and no UPDATE / DELETE grant at all
CREATE POLICY events_owner_read   ON app.events FOR SELECT TO authenticated
  USING (user_id = auth.uid());
CREATE POLICY events_owner_insert ON app.events FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- ===== Grants (plan P6): start from nothing, then exactly what each action needs =================

REVOKE ALL ON app.posts, app.wishlist_items, app.user_genre_prefs, app.events
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE app.posts_id_seq, app.events_id_seq FROM PUBLIC, anon, authenticated;

GRANT SELECT ON app.posts, app.wishlist_items, app.user_genre_prefs, app.events TO authenticated;
GRANT INSERT (author_id, title_id, season_number, rating, opinion, contains_spoilers, is_shared)
    ON app.posts TO authenticated;
GRANT UPDATE (rating, opinion, contains_spoilers, is_shared, updated_at) ON app.posts TO authenticated;
GRANT DELETE ON app.posts TO authenticated;
GRANT INSERT ON app.wishlist_items TO authenticated;
GRANT UPDATE (status, watched_at) ON app.wishlist_items TO authenticated;
GRANT DELETE ON app.wishlist_items TO authenticated;
GRANT INSERT, DELETE ON app.user_genre_prefs TO authenticated;
GRANT INSERT ON app.events TO authenticated;
GRANT USAGE ON SEQUENCE app.posts_id_seq, app.events_id_seq TO authenticated;

GRANT ALL ON app.posts, app.wishlist_items, app.user_genre_prefs, app.events TO service_role;
GRANT USAGE, SELECT ON SEQUENCE app.posts_id_seq, app.events_id_seq TO service_role;
