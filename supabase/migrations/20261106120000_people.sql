-- Phase 2: people, follows and notifications. DDL copied verbatim from spec 02 §6.
-- RLS enforces rules 00 R1, R2 and R5; column-level GRANTs (plan P6) limit what a user may write;
-- notifications are written only by SECURITY DEFINER triggers on app.follows (plan P7).

-- ===== Tables (verbatim from spec 02 §6) =========================================================

-- Card: the ONLY fields any signed-in user may see (rule R1.2)
CREATE TABLE app.profiles (
    id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username      TEXT UNIQUE NOT NULL CHECK (username ~ '^[a-z0-9_.]{3,30}$'),
    display_name  TEXT NOT NULL,
    avatar_url    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Followers-only details
CREATE TABLE app.profile_details (
    user_id UUID PRIMARY KEY REFERENCES app.profiles(id) ON DELETE CASCADE,
    bio     TEXT CHECK (char_length(bio) <= 300)
);
-- Owner-only settings
CREATE TABLE app.user_settings (
    user_id UUID PRIMARY KEY REFERENCES app.profiles(id) ON DELETE CASCADE,
    locale  TEXT NOT NULL DEFAULT 'he' CHECK (locale IN ('he','en'))
);

-- One-way follow, approval required (rule R2)
CREATE TABLE app.follows (
    follower_id  UUID NOT NULL REFERENCES app.profiles(id) ON DELETE CASCADE,
    followee_id  UUID NOT NULL REFERENCES app.profiles(id) ON DELETE CASCADE,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    responded_at TIMESTAMPTZ,
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id <> followee_id)
);
-- decline / cancel / unfollow / remove follower = DELETE the row

CREATE TABLE app.notifications (
    id           BIGSERIAL PRIMARY KEY,
    recipient_id UUID NOT NULL REFERENCES app.profiles(id) ON DELETE CASCADE,
    actor_id     UUID NOT NULL REFERENCES app.profiles(id) ON DELETE CASCADE,
    type         TEXT NOT NULL CHECK (type IN ('follow_request','follow_accepted')),
    read_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- filled by triggers on app.follows (INSERT → follow_request, UPDATE to accepted → follow_accepted);
-- a request's notification is deleted if the request is cancelled or declined

-- ===== Row-level security ========================================================================

ALTER TABLE app.profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.profile_details ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.user_settings   ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.follows         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.notifications   ENABLE ROW LEVEL SECURITY;

-- helper: is the current user an APPROVED follower of :target?  (body verbatim from spec 02 §6)
CREATE FUNCTION app.follows_approved(target UUID) RETURNS BOOLEAN
LANGUAGE sql STABLE SET search_path = '' AS $$
  SELECT EXISTS (SELECT 1 FROM app.follows
                 WHERE follower_id = auth.uid() AND followee_id = target AND status = 'accepted')
$$;
REVOKE EXECUTE ON FUNCTION app.follows_approved(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app.follows_approved(UUID) TO authenticated;

-- profiles (card): any signed-in user may read; only owner may write
CREATE POLICY card_read   ON app.profiles FOR SELECT TO authenticated USING (true);
CREATE POLICY card_write  ON app.profiles FOR UPDATE TO authenticated
  USING (id = auth.uid()) WITH CHECK (id = auth.uid());
CREATE POLICY card_insert ON app.profiles FOR INSERT TO authenticated WITH CHECK (id = auth.uid());

-- profile_details: owner or approved follower may read; only owner may write
CREATE POLICY details_read ON app.profile_details FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR app.follows_approved(user_id));
CREATE POLICY details_owner_insert ON app.profile_details FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());
CREATE POLICY details_owner_update ON app.profile_details FOR UPDATE TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- user_settings: owner only
CREATE POLICY settings_owner ON app.user_settings FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- follows: only the two people involved can see a row
CREATE POLICY follows_read    ON app.follows FOR SELECT TO authenticated
  USING (auth.uid() IN (follower_id, followee_id));
CREATE POLICY follows_request ON app.follows FOR INSERT TO authenticated
  WITH CHECK (follower_id = auth.uid() AND status = 'pending');
CREATE POLICY follows_accept  ON app.follows FOR UPDATE TO authenticated
  USING (followee_id = auth.uid()) WITH CHECK (status = 'accepted');
CREATE POLICY follows_delete  ON app.follows FOR DELETE TO authenticated
  USING (auth.uid() IN (follower_id, followee_id));   -- unfollow / cancel / decline / remove

-- notifications: recipient only (read, mark read); nobody inserts except the triggers below
CREATE POLICY notif_owner     ON app.notifications FOR SELECT TO authenticated
  USING (recipient_id = auth.uid());
CREATE POLICY notif_mark_read ON app.notifications FOR UPDATE TO authenticated
  USING (recipient_id = auth.uid()) WITH CHECK (recipient_id = auth.uid());

-- ===== Grants (plan P6): start from nothing, then exactly the columns each action needs ==========

REVOKE ALL ON app.profiles, app.profile_details, app.user_settings, app.follows, app.notifications
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON SEQUENCE app.notifications_id_seq FROM PUBLIC, anon, authenticated;

GRANT SELECT ON app.profiles, app.profile_details, app.user_settings, app.follows, app.notifications
    TO authenticated;
GRANT INSERT (id, username, display_name, avatar_url) ON app.profiles TO authenticated;
GRANT UPDATE (display_name, avatar_url)               ON app.profiles TO authenticated;
GRANT INSERT (user_id, bio)                           ON app.profile_details TO authenticated;
GRANT UPDATE (bio)                                    ON app.profile_details TO authenticated;
GRANT INSERT (user_id, locale)                        ON app.user_settings TO authenticated;
GRANT UPDATE (locale)                                 ON app.user_settings TO authenticated;
GRANT INSERT (follower_id, followee_id)               ON app.follows TO authenticated;
GRANT UPDATE (status)                                 ON app.follows TO authenticated;
GRANT DELETE                                          ON app.follows TO authenticated;
GRANT UPDATE (read_at)                                ON app.notifications TO authenticated;

GRANT ALL ON app.profiles, app.profile_details, app.user_settings, app.follows, app.notifications
    TO service_role;
GRANT USAGE, SELECT ON SEQUENCE app.notifications_id_seq TO service_role;

-- ===== Follow triggers (plan P7) =================================================================
-- SECURITY DEFINER so they can write notifications the acting user has no INSERT/DELETE on;
-- empty search_path with fully qualified names so a caller cannot redirect what they touch.

-- New request → notify the person being followed.
CREATE FUNCTION app.follows_notify_request() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  INSERT INTO app.notifications (recipient_id, actor_id, type)
  VALUES (NEW.followee_id, NEW.follower_id, 'follow_request');
  RETURN NULL;
END
$$;

-- Status may only go pending → accepted (stamps responded_at). Re-accepting is a no-op that
-- keeps the row exactly as it was; any other status change is refused.
CREATE FUNCTION app.follows_guard_status() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  IF OLD.status = 'pending' AND NEW.status = 'accepted' THEN
    NEW.responded_at := pg_catalog.now();
    RETURN NEW;
  ELSIF OLD.status = 'accepted' AND NEW.status = 'accepted' THEN
    RETURN OLD;
  END IF;
  RAISE EXCEPTION 'follow status cannot change from % to %', OLD.status, NEW.status
    USING ERRCODE = 'check_violation';
END
$$;

-- Accepted → notify the follower.
CREATE FUNCTION app.follows_notify_accepted() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  INSERT INTO app.notifications (recipient_id, actor_id, type)
  VALUES (NEW.follower_id, NEW.followee_id, 'follow_accepted');
  RETURN NULL;
END
$$;

-- Row gone (cancel / decline / unfollow / remove) → its request notification goes too.
-- follow_accepted notifications stay.
CREATE FUNCTION app.follows_clear_request() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  DELETE FROM app.notifications
  WHERE recipient_id = OLD.followee_id AND actor_id = OLD.follower_id AND type = 'follow_request';
  RETURN NULL;
END
$$;

REVOKE EXECUTE ON FUNCTION app.follows_notify_request(), app.follows_guard_status(),
    app.follows_notify_accepted(), app.follows_clear_request() FROM PUBLIC, anon, authenticated;

CREATE TRIGGER follows_notify_request AFTER INSERT ON app.follows
    FOR EACH ROW EXECUTE FUNCTION app.follows_notify_request();
CREATE TRIGGER follows_guard_status BEFORE UPDATE ON app.follows
    FOR EACH ROW EXECUTE FUNCTION app.follows_guard_status();
CREATE TRIGGER follows_notify_accepted AFTER UPDATE ON app.follows
    FOR EACH ROW WHEN (OLD.status = 'pending' AND NEW.status = 'accepted')
    EXECUTE FUNCTION app.follows_notify_accepted();
CREATE TRIGGER follows_clear_request AFTER DELETE ON app.follows
    FOR EACH ROW EXECUTE FUNCTION app.follows_clear_request();
