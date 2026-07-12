-- Store detected score orientation for convert, cache reuse, and layout.
-- Safe to run once on existing production databases.
USE partifi;

ALTER TABLE scores
  ADD COLUMN orientation ENUM('portrait', 'landscape') NOT NULL DEFAULT 'portrait' AFTER s3;
