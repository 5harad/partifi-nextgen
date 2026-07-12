-- Per-partset page orientation override (does not change scores.orientation).
ALTER TABLE partsets
  ADD COLUMN orientation_override ENUM('portrait', 'landscape') NULL AFTER paste_progress,
  ADD COLUMN rotation_degrees INT NOT NULL DEFAULT 0 AFTER orientation_override;
