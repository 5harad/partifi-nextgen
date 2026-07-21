ALTER TABLE partsets
    ADD COLUMN split_two_up BOOLEAN NOT NULL DEFAULT 0 AFTER rotation_degrees;
