-- Phase 3: rules the posts table cannot state as a CHECK, and the indexes Home, the title page and
-- notifications need (plan P1-P3).
-- Both trigger functions are SECURITY INVOKER: they read only the catalogue, which `authenticated`
-- may SELECT. Empty search_path with fully qualified names, like the Phase 2 functions.

-- ===== Season check (P1): spec 02 §6 "app check (in a trigger)" ==================================
-- season_number 0 = the whole movie / series; > 0 only for a series that has that season cached.
-- On UPDATE it re-checks only when title_id or season_number actually change, so a later catalogue
-- refresh that drops a season never blocks an edit of an existing post.
-- CONSTRAINT lets the API read `diag.constraint_name` and answer 422 season_invalid.

CREATE FUNCTION app.posts_check_season() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF TG_OP = 'UPDATE'
     AND NEW.title_id = OLD.title_id AND NEW.season_number = OLD.season_number THEN
    RETURN NEW;
  END IF;
  IF NEW.season_number < 0 THEN
    RAISE EXCEPTION 'season_number must not be negative'
      USING ERRCODE = 'check_violation', CONSTRAINT = 'posts_season_valid';
  END IF;
  IF NEW.season_number > 0 AND NOT EXISTS (
       SELECT 1
       FROM app.titles t
       JOIN app.title_seasons s ON s.title_id = t.id
       WHERE t.id = NEW.title_id
         AND t.media_type = 'series'
         AND s.season_number = NEW.season_number
     ) THEN
    RAISE EXCEPTION 'season % does not exist for title %', NEW.season_number, NEW.title_id
      USING ERRCODE = 'check_violation', CONSTRAINT = 'posts_season_valid';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER posts_check_season
  BEFORE INSERT OR UPDATE OF title_id, season_number ON app.posts
  FOR EACH ROW EXECUTE FUNCTION app.posts_check_season();

-- ===== updated_at (P2) ===========================================================================
-- Moves only when the content really changes, so a no-op save does not mark the post "edited".
-- Users lose UPDATE (updated_at): the trigger is the only writer.

CREATE FUNCTION app.posts_touch_updated_at() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF (NEW.rating, NEW.opinion, NEW.contains_spoilers, NEW.is_shared)
     IS DISTINCT FROM (OLD.rating, OLD.opinion, OLD.contains_spoilers, OLD.is_shared) THEN
    NEW.updated_at := now();
  ELSE
    NEW.updated_at := OLD.updated_at;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER posts_touch_updated_at
  BEFORE UPDATE ON app.posts
  FOR EACH ROW EXECUTE FUNCTION app.posts_touch_updated_at();

REVOKE UPDATE (updated_at) ON app.posts FROM authenticated;

-- ===== Indexes (P3) ==============================================================================

CREATE INDEX notifications_recipient_created_idx
    ON app.notifications (recipient_id, created_at DESC, id DESC);
CREATE INDEX follows_followee_idx ON app.follows (followee_id);
CREATE INDEX posts_title_created_idx ON app.posts (title_id, created_at DESC);
