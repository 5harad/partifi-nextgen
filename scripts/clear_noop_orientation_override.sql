-- Clear orientation_override when the partset is not actually rotated.
-- Override should only be set for rotation_degrees != 0.
UPDATE partsets
SET orientation_override = NULL
WHERE IFNULL(rotation_degrees, 0) = 0
  AND orientation_override IS NOT NULL;
