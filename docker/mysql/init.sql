CREATE DATABASE IF NOT EXISTS partifi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE partifi;

-- String ids (scores, partsets, URL path segments) use utf8mb4_bin so legacy ids
-- that differ only by case (e.g. 03mra vs 03mrA) remain distinct. Text search
-- columns keep utf8mb4_unicode_ci.

CREATE TABLE IF NOT EXISTS scores (
    id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    imslp_id VARCHAR(255),
    num_pages INT,
    file_size INT,
    file_hash VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    import_start DATETIME,
    import_complete DATETIME,
    convert_start DATETIME,
    convert_complete DATETIME,
    analysis_start DATETIME,
    analysis_complete DATETIME,
    num_downloads INT NOT NULL DEFAULT 0,
    s3 BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE KEY uq_scores_file_hash (file_hash),
    INDEX idx_scores_imslp_id (imslp_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS partsets (
    id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    private_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    imslp_id VARCHAR(255),
    tmpdir VARCHAR(255),
    create_ts DATETIME,
    mod_ts DATETIME,
    last_access DATETIME,
    parts_ready BOOLEAN DEFAULT 0,
    title VARCHAR(255),
    composer VARCHAR(255),
    publisher VARCHAR(255),
    copyright ENUM('before 1923', 'after 1923', 'unknown'),
    user_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    num_downloads INT NOT NULL DEFAULT 0,
    status ENUM('import', 'convert', 'analysis', 'cut', 'paste'),
    error ENUM('import', 'import_size', 'convert', 'analysis', 'cut', 'paste'),
    error_message VARCHAR(512),
    error_ts DATETIME,
    last_job_id VARCHAR(32),
    import_start DATETIME,
    import_complete DATETIME,
    import_progress FLOAT NOT NULL DEFAULT 0,
    convert_start DATETIME,
    convert_complete DATETIME,
    convert_progress FLOAT NOT NULL DEFAULT 0,
    analysis_start DATETIME,
    analysis_complete DATETIME,
    analysis_progress FLOAT NOT NULL DEFAULT 0,
    cut_start DATETIME,
    cut_complete DATETIME,
    cut_progress FLOAT NOT NULL DEFAULT 0,
    paste_start DATETIME,
    paste_complete DATETIME,
    paste_progress FLOAT NOT NULL DEFAULT 0,
    INDEX idx_partsets_score_id (score_id),
    UNIQUE KEY uq_partsets_private_id (private_id),
    INDEX idx_partsets_last_access (last_access),
    INDEX idx_partsets_paste_complete (paste_complete),
    INDEX idx_partsets_analysis_complete (analysis_complete),
    INDEX idx_partsets_create_ts (create_ts),
    INDEX idx_partsets_mod_ts (mod_ts),
    FULLTEXT idx_partsets_search (title, composer, publisher, imslp_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS original_pages (
    score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    page INT,
    left_margin FLOAT,
    right_margin FLOAT,
    rotation FLOAT,
    PRIMARY KEY (score_id, page)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS original_segments (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    page INT,
    top FLOAT,
    bottom FLOAT,
    INDEX idx_original_segments_score_id (score_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pages (
    partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    page INT,
    left_margin FLOAT,
    right_margin FLOAT,
    rotation FLOAT,
    PRIMARY KEY (partset_id, page)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS segments (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    page INT,
    top FLOAT,
    bottom FLOAT,
    tags VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    tag_is_suggestion BOOLEAN NOT NULL DEFAULT 0,
    label VARCHAR(255),
    label_is_suggestion BOOLEAN NOT NULL DEFAULT 0,
    INDEX idx_segments_partset_id (partset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS breaks (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    tag VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    break INT,
    INDEX idx_breaks_partset_id (partset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS parts (
    partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    tag VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    spacing FLOAT,
    combined BOOLEAN,
    file_name VARCHAR(255),
    PRIMARY KEY (partset_id, tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS downloads (
    score_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    tag VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    user_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    bcookie VARCHAR(255),
    ts DATETIME,
    INDEX idx_downloads_score_id (score_id),
    INDEX idx_downloads_partset_tag (partset_id, tag),
    INDEX idx_downloads_ts (ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS imslp_info (
    id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    title VARCHAR(255),
    composer VARCHAR(255),
    publisher VARCHAR(255),
    copyright VARCHAR(255),
    url VARCHAR(255),
    file_type VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS favorites (
    partset_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    user_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    admin BOOLEAN,
    ts DATETIME,
    PRIMARY KEY (partset_id, user_id),
    INDEX idx_favorites_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL PRIMARY KEY,
    name VARCHAR(255),
    given_name VARCHAR(255),
    ts DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS friends (
    u1 VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    u2 VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
    PRIMARY KEY (u1, u2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS composers (
    composer VARCHAR(255) NOT NULL PRIMARY KEY,
    popularity INT NOT NULL,
    FULLTEXT idx_composers_composer (composer)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
