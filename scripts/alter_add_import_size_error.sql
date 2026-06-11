-- Add import_size to partsets.error (oversize IMSLP/PDF rejections during import).
-- Safe to run once on existing production databases.
USE partifi;

ALTER TABLE partsets
  MODIFY error ENUM(
    'import',
    'import_size',
    'convert',
    'analysis',
    'cut',
    'paste'
  );
