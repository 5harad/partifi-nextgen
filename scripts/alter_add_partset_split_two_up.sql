-- partsets has a FULLTEXT index, so INSTANT/INPLACE ADD COLUMN is not available.
-- Expect a multi-minute table rebuild; run during a quiet window.
ALTER TABLE partsets
    ADD COLUMN split_two_up BOOLEAN NOT NULL DEFAULT 0 AFTER rotation_degrees,
    ALGORITHM=COPY;
