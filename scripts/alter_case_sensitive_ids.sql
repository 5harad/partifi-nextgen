-- Run once on an existing prod MySQL before legacy import if the database was
-- created from an older init.sql (utf8mb4_unicode_ci on id columns).
-- Requires empty content tables (TRUNCATE or fresh volume).
--
--   docker compose -f docker-compose.prod.yml exec -T mysql \
--     mysql -u root -p"$MYSQL_ROOT_PASSWORD" partifi < scripts/alter_case_sensitive_ids.sql

USE partifi;

ALTER TABLE scores
  MODIFY id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  MODIFY file_hash VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

ALTER TABLE partsets
  MODIFY id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  MODIFY private_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  MODIFY score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  MODIFY user_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

ALTER TABLE original_pages
  MODIFY score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;

ALTER TABLE original_segments
  MODIFY score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;

ALTER TABLE pages
  MODIFY partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;

ALTER TABLE segments
  MODIFY partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  MODIFY tags VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

ALTER TABLE breaks
  MODIFY partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  MODIFY tag VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

ALTER TABLE parts
  MODIFY partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  MODIFY tag VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;

ALTER TABLE imslp_info
  MODIFY id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL;
