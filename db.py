"""
Database helper module for SaveMedia
Handles MySQL connection pooling and all DB operations.
"""

import os
import mysql.connector
from mysql.connector import pooling, Error
from datetime import datetime, date
from dotenv import load_dotenv
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# ── Configuration ──────────────────────────────────────────
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'savemedia_db'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True,
}

# Connection pool (reuses connections for performance)
pool = None


def init_pool(pool_size=5):
    """Initialize the connection pool."""
    global pool
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="savemedia_pool",
            pool_size=pool_size,
            pool_reset_session=True,
            **DB_CONFIG
        )
        print("[DB] Connection pool created successfully")
        return True
    except Error as e:
        print(f"[DB] Pool creation failed: {e}")
        return False


def get_connection():
    """Get a connection from the pool."""
    global pool
    if pool is None:
        init_pool()
    try:
        return pool.get_connection()
    except Error as e:
        print(f"[DB] Connection error: {e}")
        return None

@contextmanager
def get_db_connection():
    """Context manager for DB connections to prevent leaks."""
    conn = get_connection()
    try:
        yield conn
    finally:
        if conn:
            conn.close()


def init_database():
    """Create the database and tables if they don't exist."""
    try:
        # First connect without specifying database to create it
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
        )
        cursor = conn.cursor()
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS savemedia_db "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute("USE savemedia_db")

        # Create tables
        cursor.execute("""
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
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                page        VARCHAR(100) DEFAULT '/',
                ip_address  VARCHAR(45) DEFAULT NULL,
                user_agent  VARCHAR(500) DEFAULT NULL,
                referrer    VARCHAR(2048) DEFAULT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_page (page),
                INDEX idx_created (created_at)
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
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
            ) ENGINE=InnoDB
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("[DB] Database and tables initialized")
        return True
    except Error as e:
        print(f"[DB] Init error: {e}")
        return False


# ── CRUD Operations ────────────────────────────────────────

def purge_old_data(days=90):
    """Delete page views and downloads older than specified days."""
    with get_db_connection() as conn:
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM page_views WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (days,)
            )
            cursor.execute(
                "DELETE FROM downloads WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)", (days,)
            )
            conn.commit()
            cursor.close()
        except Error as e:
            print(f"[DB] Purge error: {e}")

def log_page_view(page='/', ip=None, user_agent=None, referrer=None):
    """Record a page view."""
    with get_db_connection() as conn:
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO page_views (page, ip_address, user_agent, referrer) "
                "VALUES (%s, %s, %s, %s)",
                (page, ip, (user_agent or '')[:500], (referrer or '')[:2048])
            )
            conn.commit()
            cursor.close()
            
            # Update daily stats
            update_daily_stats('view')
        except Error as e:
            print(f"[DB] Page view log error: {e}")


def log_download(url, platform, media_type='video', title=None,
                 quality=None, ip=None, user_agent=None,
                 status='success', error_msg=None):
    """Record a download attempt."""
    with get_db_connection() as conn:
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO downloads "
                "(url, platform, media_type, title, quality, ip_address, "
                "user_agent, status, error_msg) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (url[:2048], platform, media_type, (title or '')[:500],
                 quality, ip, (user_agent or '')[:500], status,
                 error_msg)
            )
            conn.commit()
            cursor.close()
            
            if status == 'success':
                update_daily_stats('download', platform)
        except Error as e:
            print(f"[DB] Download log error: {e}")

def update_daily_stats(stat_type, platform=None):
    """Increment daily stats counters."""
    with get_db_connection() as conn:
        if not conn: return
        try:
            cursor = conn.cursor()
            today = date.today().isoformat()
            
            # Insert if not exists
            cursor.execute(
                "INSERT IGNORE INTO daily_stats (stat_date) VALUES (%s)", (today,)
            )
            
            if stat_type == 'view':
                cursor.execute(
                    "UPDATE daily_stats SET total_views = total_views + 1 WHERE stat_date = %s", (today,)
                )
            elif stat_type == 'download':
                cursor.execute(
                    "UPDATE daily_stats SET total_downloads = total_downloads + 1 WHERE stat_date = %s", (today,)
                )
                if platform in ['instagram', 'youtube', 'pinterest', 'facebook']:
                    col = f"{platform}_dl"
                    cursor.execute(
                        f"UPDATE daily_stats SET {col} = {col} + 1 WHERE stat_date = %s", (today,)
                    )
                    
            conn.commit()
            cursor.close()
        except Error as e:
            print(f"[DB] Daily stats update error: {e}")


def get_stats_today():
    """Get today's download and view stats."""
    with get_db_connection() as conn:
        if not conn: return {}
        try:
            cursor = conn.cursor(dictionary=True)
            today = date.today().isoformat()

            # Total downloads today
            cursor.execute(
                "SELECT COUNT(*) as total FROM downloads "
                "WHERE DATE(created_at) = %s AND status='success'", (today,)
            )
            total_dl = cursor.fetchone()['total']

            # Downloads by platform today
            cursor.execute(
                "SELECT platform, COUNT(*) as count FROM downloads "
                "WHERE DATE(created_at) = %s AND status='success' "
                "GROUP BY platform", (today,)
            )
            platform_stats = {row['platform']: row['count'] for row in cursor.fetchall()}

            # Page views today
            cursor.execute(
                "SELECT COUNT(*) as total FROM page_views "
                "WHERE DATE(created_at) = %s", (today,)
            )
            total_views = cursor.fetchone()['total']

            # Unique visitors today
            cursor.execute(
                "SELECT COUNT(DISTINCT ip_address) as total FROM page_views "
                "WHERE DATE(created_at) = %s", (today,)
            )
            unique = cursor.fetchone()['total']

            cursor.close()

            return {
                'date': today,
                'total_downloads': total_dl,
                'total_views': total_views,
                'unique_visitors': unique,
                'instagram': platform_stats.get('instagram', 0),
                'youtube': platform_stats.get('youtube', 0),
                'pinterest': platform_stats.get('pinterest', 0),
                'facebook': platform_stats.get('facebook', 0),
            }
        except Error as e:
            print(f"[DB] Stats error: {e}")
            return {}


def get_stats_range(days=7):
    """Get stats for the last N days."""
    with get_db_connection() as conn:
        if not conn: return []
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT DATE(created_at) as day, COUNT(*) as downloads "
                "FROM downloads WHERE status='success' "
                "AND created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY DATE(created_at) ORDER BY day", (days,)
            )
            results = cursor.fetchall()
            # Convert date objects to strings
            for row in results:
                row['day'] = row['day'].isoformat()
            cursor.close()
            return results
        except Error as e:
            print(f"[DB] Range stats error: {e}")
            return []


def get_recent_downloads(limit=20):
    """Get the most recent downloads."""
    with get_db_connection() as conn:
        if not conn: return []
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, platform, media_type, title, quality, status, "
                "created_at FROM downloads ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            results = cursor.fetchall()
            for row in results:
                row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            cursor.close()
            return results
        except Error as e:
            print(f"[DB] Recent downloads error: {e}")
            return []


def get_all_time_stats():
    """Get all-time totals."""
    with get_db_connection() as conn:
        if not conn: return {}
        try:
            cursor = conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT COUNT(*) as total FROM downloads WHERE status='success'"
            )
            total = cursor.fetchone()['total']

            cursor.execute(
                "SELECT platform, COUNT(*) as count FROM downloads "
                "WHERE status='success' GROUP BY platform"
            )
            by_platform = {row['platform']: row['count'] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) as total FROM page_views")
            views = cursor.fetchone()['total']

            cursor.close()

            return {
                'total_downloads': total,
                'total_views': views,
                'instagram': by_platform.get('instagram', 0),
                'youtube': by_platform.get('youtube', 0),
                'pinterest': by_platform.get('pinterest', 0),
                'facebook': by_platform.get('facebook', 0),
            }
        except Error as e:
            print(f"[DB] All-time stats error: {e}")
            return {}
