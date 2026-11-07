-- Phase 4: rules the wishlist table cannot state as a CHECK (plan P1-P2).
-- Both trigger functions are SECURITY INVOKER with an empty search_path and fully qualified
-- names, like the Phase 3 ones.

-- ===== Source check (P1) =========================================================================
-- A wishlist item saved "from a post" must point at a post the saver can SEE, on the same title.
-- SECURITY INVOKER on purpose: the lookup runs under the caller's RLS, so a post they may not see
-- is indistinguishable from one that does not exist. One fixed message, no ids in it.
-- Fires on INSERT only: ON DELETE SET NULL later clears source_post_id (the post was deleted) and
-- must not be blocked, which is also why the CHECK below allows source 'post' with no post.
-- CONSTRAINT lets the API read `diag.constraint_name` and answer 422 source_invalid.

CREATE FUNCTION app.wishlist_check_source() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF NEW.source = 'post' THEN
    IF NEW.source_post_id IS NULL OR NOT EXISTS (
         SELECT 1 FROM app.posts p
         WHERE p.id = NEW.source_post_id AND p.title_id = NEW.title_id
       ) THEN
      RAISE EXCEPTION 'source post is missing or not visible on this title'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'wishlist_source_valid';
    END IF;
  ELSIF NEW.source_post_id IS NOT NULL THEN
    RAISE EXCEPTION 'source post is missing or not visible on this title'
      USING ERRCODE = 'check_violation', CONSTRAINT = 'wishlist_source_valid';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER wishlist_check_source
  BEFORE INSERT ON app.wishlist_items
  FOR EACH ROW EXECUTE FUNCTION app.wishlist_check_source();

ALTER TABLE app.wishlist_items
  ADD CONSTRAINT wishlist_source_post_only_for_posts
  CHECK (source = 'post' OR source_post_id IS NULL);

-- ===== watched_at (P2) ===========================================================================
-- The clock follows status: stamped when an item becomes 'watched', kept while it stays watched,
-- cleared when it goes back to anything else. Users lose UPDATE (watched_at): the trigger is the
-- only writer.

CREATE FUNCTION app.wishlist_touch_watched_at() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF NEW.status <> 'watched' THEN
    NEW.watched_at := NULL;
  ELSIF TG_OP = 'UPDATE' AND OLD.status = 'watched' THEN
    NEW.watched_at := OLD.watched_at;
  ELSE
    NEW.watched_at := now();
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER wishlist_touch_watched_at
  BEFORE INSERT OR UPDATE ON app.wishlist_items
  FOR EACH ROW EXECUTE FUNCTION app.wishlist_touch_watched_at();

REVOKE UPDATE (watched_at) ON app.wishlist_items FROM authenticated;
