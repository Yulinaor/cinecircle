-- Phase 6 (plan P7): when the review was written on TMDB, so "newest first" means newest review.
-- NULL when TMDB sent no date. No grant change: the table-level SELECT covers the new column.

ALTER TABLE app.external_reviews ADD COLUMN published_at TIMESTAMPTZ;
