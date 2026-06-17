-- Google given_name for greeting display (backfilled on next login).
-- Safe to run once on existing production databases.
USE partifi;

ALTER TABLE users
  ADD COLUMN given_name VARCHAR(255) NULL AFTER name;
