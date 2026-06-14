-- Richer failure metadata on partsets (support / diagnostics).
-- Safe to run once on existing production databases.
USE partifi;

ALTER TABLE partsets
  ADD COLUMN error_message VARCHAR(512) NULL AFTER error,
  ADD COLUMN error_ts DATETIME NULL AFTER error_message,
  ADD COLUMN last_job_id VARCHAR(32) NULL AFTER error_ts;
