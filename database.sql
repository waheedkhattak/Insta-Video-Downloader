-- SaveMedia Database Setup
-- Run this in phpMyAdmin or MySQL CLI

CREATE DATABASE IF NOT EXISTS savemedia_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE savemedia_db;

-- Download history log
CREATE TABLE IF NOT EXISTS downloads (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    url         VARCHAR(2048) NOT NULL,
    platform    ENUM('instagram','youtube','pinterest','facebook') NOT NULL,
    media_type  ENUM('video','image') DEFAULT 'video',
    title       VARCHAR(500) DEFAULT NULL,
    quality     VARCHAR(20) DEFAULT NULL,
    ip_address  VARCHAR(45) DEFAULT NULL,
    user_agent  VARCHAR(500) DEFAULT NULL,
    status      ENUM('success','failed') DEFAULT 'success',
    error_msg   TEXT DEFAULT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_platform (platform),
    INDEX idx_created (created_at),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- Page views / analytics
CREATE TABLE IF NOT EXISTS page_views (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    page        VARCHAR(100) DEFAULT '/',
    ip_address  VARCHAR(45) DEFAULT NULL,
    user_agent  VARCHAR(500) DEFAULT NULL,
    referrer    VARCHAR(2048) DEFAULT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_page (page),
    INDEX idx_created (created_at)
) ENGINE=InnoDB;

-- Daily stats summary (updated by app)
CREATE TABLE IF NOT EXISTS daily_stats (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    stat_date       DATE NOT NULL UNIQUE,
    total_views     INT DEFAULT 0,
    total_downloads INT DEFAULT 0,
    instagram_dl    INT DEFAULT 0,
    youtube_dl      INT DEFAULT 0,
    pinterest_dl    INT DEFAULT 0,
    facebook_dl     INT DEFAULT 0,
    unique_visitors INT DEFAULT 0,
    INDEX idx_date (stat_date)
) ENGINE=InnoDB;
