"""
Multi-Platform Media Downloader
Supports: Instagram, YouTube, Pinterest, Facebook
Backend powered by Flask + yt-dlp + MySQL
"""

from flask import (Flask, render_template, request, jsonify,
                   send_file, after_this_request, session, redirect, url_for, Response)
import yt_dlp
import os
import uuid
import threading
import time
import logging
from functools import wraps
from urllib.parse import urlparse
from dotenv import load_dotenv
import db  # Database module

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ===================== SECURITY CONFIG =====================

# Admin credentials from environment
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'savemedia2026')

# Rate limiting (graceful fallback if not installed)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per hour"],
        storage_uri="memory://"
    )
    logger.info("[Security] Rate limiting enabled")
except ImportError:
    logger.warning("[Security] flask-limiter not installed — run: pip install flask-limiter")
    class _NoOpLimiter:
        def limit(self, *a, **kw):
            def decorator(f): return f
            return decorator
    limiter = _NoOpLimiter()

# Allowed domains for URL validation (SSRF prevention)
ALLOWED_DOMAINS = [
    'instagram.com', 'www.instagram.com', 'instagr.am',
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    'music.youtube.com',
    'pinterest.com', 'www.pinterest.com', 'pin.it',
    'facebook.com', 'www.facebook.com', 'm.facebook.com',
    'fb.watch', 'fb.com', 'www.fb.com', 'web.facebook.com',
]

# Create downloads folder
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


active_downloads = {}

def cleanup_old_files():
    """Remove downloaded files and old jobs older than 10 minutes."""
    loops = 0
    while True:
        time.sleep(60)
        loops += 1
        try:
            now = time.time()
            # Clean files
            for filename in os.listdir(DOWNLOAD_DIR):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                if os.path.isfile(filepath) and now - os.path.getmtime(filepath) > 600:
                    os.remove(filepath)
                    logger.info(f"[Cleanup] Removed old file: {filename}")
            
            # Clean old jobs
            jobs_to_remove = [k for k, v in active_downloads.items() if now - v.get('timestamp', now) > 600]
            for k in jobs_to_remove:
                del active_downloads[k]
                
            # Purge old database records every 24 hours (1440 loops of 60s)
            if loops >= 1440:
                db.purge_old_data(days=90)
                loops = 0
        except Exception as e:
            logger.error(f"[Cleanup] Error: {e}")


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()


# ===================== SECURITY HELPERS =====================

def detect_platform(url):
    """Detect which platform a URL belongs to."""
    url_lower = url.lower()
    if any(domain in url_lower for domain in ['instagram.com', 'instagr.am']):
        return 'instagram'
    elif any(domain in url_lower for domain in ['youtube.com', 'youtu.be', 'youtube.com/shorts']):
        return 'youtube'
    elif any(domain in url_lower for domain in ['pinterest.com', 'pin.it']):
        return 'pinterest'
    elif any(domain in url_lower for domain in ['facebook.com', 'fb.watch', 'fb.com', 'fbcdn.net']):
        return 'facebook'
    return None


def get_client_ip():
    """Get the real client IP address."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr


def validate_url(url):
    """Validate URL format and domain to prevent SSRF attacks."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False, 'Only HTTP and HTTPS URLs are allowed.'
        hostname = parsed.hostname
        if not hostname:
            return False, 'Invalid URL format.'
        # Check against allowed domains
        if not any(hostname == d or hostname.endswith('.' + d) for d in ALLOWED_DOMAINS):
            return False, 'Unsupported platform. Use Instagram, YouTube, Pinterest, or Facebook URLs.'
        return True, None
    except Exception:
        return False, 'Invalid URL format.'


def require_admin(f):
    """Decorator to require admin authentication for routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ===================== MEDIA HELPERS =====================

def get_media_info(url, platform):
    """Extract media information without downloading."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    # Platform-specific options
    if platform == 'youtube':
        ydl_opts['format'] = 'best[ext=mp4]/best'
    elif platform == 'instagram':
        ydl_opts['format'] = 'best'
    elif platform == 'pinterest':
        ydl_opts['format'] = 'best'
    elif platform == 'facebook':
        ydl_opts['format'] = 'best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Determine media type
            media_type = 'video'
            if info.get('ext') in ['jpg', 'jpeg', 'png', 'webp']:
                media_type = 'image'
            elif info.get('vcodec') == 'none' and info.get('acodec') != 'none':
                media_type = 'audio'

            # Get available formats for YouTube
            formats = []
            if platform == 'youtube' and info.get('formats'):
                seen = set()
                for f in info['formats']:
                    if f.get('height') and f.get('ext') == 'mp4' and f.get('vcodec') != 'none':
                        quality = f"{f['height']}p"
                        if quality not in seen:
                            seen.add(quality)
                            formats.append({
                                'format_id': f['format_id'],
                                'quality': quality,
                                'height': f['height'],
                                'ext': f.get('ext', 'mp4'),
                                'filesize': f.get('filesize') or f.get('filesize_approx', 0)
                            })
                formats.sort(key=lambda x: x['height'], reverse=True)

            thumbnail = info.get('thumbnail', '')
            # For Instagram, try to get a better thumbnail
            if not thumbnail and info.get('thumbnails'):
                thumbnail = info['thumbnails'][-1].get('url', '')

            return {
                'success': True,
                'title': info.get('title', 'Untitled'),
                'thumbnail': thumbnail,
                'duration': info.get('duration', 0),
                'platform': platform,
                'media_type': media_type,
                'formats': formats,
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'description': (info.get('description', '') or '')[:200],
                'stream_url': info.get('url', ''),
            }
    except Exception as e:
        logger.error(f"[Info] Error extracting info: {e}")
        return {'success': False, 'error': str(e)}


def download_media(url, platform, format_id=None, quality='best'):
    """Download media and return the file path."""
    unique_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f'{unique_id}_%(title)s.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
    }

    # Platform-specific download options
    if platform == 'youtube':
        if format_id == 'bestaudio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        elif format_id:
            ydl_opts['format'] = f'{format_id}+bestaudio[ext=m4a]/best'
            ydl_opts['merge_output_format'] = 'mp4'
        elif quality and quality != 'best':
            height = quality.replace('p', '')
            ydl_opts['format'] = f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
            ydl_opts['merge_output_format'] = 'mp4'
        else:
            ydl_opts['format'] = 'best[ext=mp4]/best'
            ydl_opts['merge_output_format'] = 'mp4'
    elif platform == 'instagram':
        ydl_opts['format'] = 'best'
    elif platform == 'pinterest':
        ydl_opts['format'] = 'best'
    elif platform == 'facebook':
        ydl_opts['format'] = 'best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            # Handle merged files
            if not os.path.exists(filename):
                # Try with .mp4 extension
                base = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.webm', '.mkv', '.jpg', '.png', '.webp']:
                    if os.path.exists(base + ext):
                        filename = base + ext
                        break

            if os.path.exists(filename):
                return {
                    'success': True,
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'title': info.get('title', 'download'),
                    'ext': os.path.splitext(filename)[1][1:],
                }
            else:
                return {'success': False, 'error': 'Download completed but file not found.'}

    except Exception as e:
        logger.error(f"[Download] Error: {e}")
        return {'success': False, 'error': str(e)}


# ===================== SEO & LEGAL ROUTES =====================

@app.route('/privacy')
def privacy():
    db.log_page_view(page='/privacy')
    content = """
    <h1>Privacy Policy</h1>
    <p>Last updated: May 2026</p>
    <h2>1. Information We Collect</h2>
    <p>We do not collect personal information. We track basic anonymous analytics (like page views and successful downloads) to improve our service.</p>
    <h2>2. Cookies and Advertising</h2>
    <p>We use third-party advertising companies (Google AdSense) to serve ads. These companies may use cookies to serve personalized ads based on your visits to our site and other sites on the Internet.</p>
    <h2>3. External Links</h2>
    <p>Our website may contain links to other sites. We are not responsible for the privacy practices of other sites.</p>
    """
    return render_template('page.html', title="Privacy Policy", content=content)

@app.route('/terms')
def terms():
    db.log_page_view(page='/terms')
    content = """
    <h1>Terms of Service</h1>
    <p>Last updated: May 2026</p>
    <h2>1. Acceptance of Terms</h2>
    <p>By using SaveMedia, you agree to these terms. If you disagree, do not use the service.</p>
    <h2>2. Use of Service</h2>
    <p>SaveMedia is intended for personal, non-commercial use. You agree not to download copyrighted material without permission from the owner.</p>
    <h2>3. Limitation of Liability</h2>
    <p>We provide this service "as is" without warranty. We are not liable for any damages resulting from the use of our service.</p>
    """
    return render_template('page.html', title="Terms of Service", content=content)

@app.route('/contact')
def contact():
    db.log_page_view(page='/contact')
    content = """
    <h1>Contact Us</h1>
    <p>If you have any questions, suggestions, or issues, please reach out to us at:</p>
    <p><strong>Email:</strong> support@savemedia.com</p>
    """
    return render_template('page.html', title="Contact Us", content=content)

@app.route('/dmca')
def dmca():
    db.log_page_view(page='/dmca')
    content = """
    <h1>DMCA Policy</h1>
    <p>SaveMedia respects intellectual property rights. We do not host any media files on our servers. Our service simply acts as a conduit to public APIs and links provided by users.</p>
    <p>If you believe that your copyrighted work has been infringed, please contact us with a formal takedown notice containing:</p>
    <ul>
        <li>A physical or electronic signature of the copyright owner.</li>
        <li>Identification of the copyrighted work.</li>
        <li>Identification of the material that is claimed to be infringing.</li>
        <li>Your contact information.</li>
    </ul>
    <p><strong>Email:</strong> legal@savemedia.com</p>
    """
    return render_template('page.html', title="DMCA", content=content)

@app.route('/robots.txt')
def robots():
    content = "User-agent: *\\nAllow: /\\nDisallow: /admin\\nDisallow: /api/\\nSitemap: https://savemedia.com/sitemap.xml"
    return Response(content, mimetype="text/plain")

@app.route('/sitemap.xml')
def sitemap():
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://savemedia.com/</loc>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://savemedia.com/privacy</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>https://savemedia.com/terms</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>https://savemedia.com/contact</loc>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>https://savemedia.com/dmca</loc>
    <priority>0.5</priority>
  </url>
</urlset>'''
    return Response(content, mimetype="application/xml")

@app.route('/ads.txt')
def ads_txt():
    return send_file('static/ads.txt')

# ===================== MAIN ROUTES =====================

@app.route('/')
def index():
    """Serve the main page and log page view."""
    db.log_page_view(
        page='/',
        ip=get_client_ip(),
        user_agent=request.headers.get('User-Agent'),
        referrer=request.referrer
    )
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
@limiter.limit("30 per minute")
def get_info():
    """Get media information from URL."""
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'success': False, 'error': 'Please provide a URL.'})

    # Validate URL (SSRF prevention)
    valid, error = validate_url(url)
    if not valid:
        return jsonify({'success': False, 'error': error})

    # Auto-detect platform
    platform = detect_platform(url)
    if not platform:
        return jsonify({'success': False, 'error': 'Unsupported platform. Please use Instagram, YouTube, Pinterest, or Facebook URLs.'})

    logger.info(f"[Info] Fetching info for {platform} URL from {get_client_ip()}")
    result = get_media_info(url, platform)
    return jsonify(result)

import requests

@app.route('/api/proxy')
def proxy_media():
    """Proxy image/video requests to bypass strict CORS/CORP headers, with Range support."""
    url = request.args.get('url')
    if not url:
        return "No URL provided", 400
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        if 'Range' in request.headers:
            headers['Range'] = request.headers['Range']

        req = requests.get(url, stream=True, headers=headers, timeout=10)

        response_headers = {
            'Content-Type': req.headers.get('Content-Type')
        }
        if 'Content-Length' in req.headers:
            response_headers['Content-Length'] = req.headers['Content-Length']
        if 'Content-Range' in req.headers:
            response_headers['Content-Range'] = req.headers['Content-Range']
        if 'Accept-Ranges' in req.headers:
            response_headers['Accept-Ranges'] = req.headers['Accept-Ranges']

        return Response(req.iter_content(chunk_size=8192), status=req.status_code, headers=response_headers)
    except Exception as e:
        logger.error(f"[Proxy] Failed to proxy {url}: {e}")
        return str(e), 500


def async_download_worker(job_id, url, platform, format_id, quality, ip, user_agent):
    """Background worker for downloading media."""
    try:
        result = download_media(url, platform, format_id, quality)

        # Log download to database
        db.log_download(
            url=url,
            platform=platform,
            media_type=result.get('ext', 'video') if result.get('success') else 'video',
            title=result.get('title'),
            quality=quality,
            ip=ip,
            user_agent=user_agent,
            status='success' if result.get('success') else 'failed',
            error_msg=result.get('error')
        )

        if result.get('success'):
            logger.info(f"[Download] Success: {result.get('title', 'Unknown')}")
            active_downloads[job_id] = {
                'status': 'completed',
                'result': result,
                'timestamp': time.time()
            }
        else:
            logger.warning(f"[Download] Failed: {result.get('error', 'Unknown error')}")
            active_downloads[job_id] = {
                'status': 'failed',
                'error': result.get('error', 'Unknown error'),
                'timestamp': time.time()
            }
    except Exception as e:
        logger.error(f"[Download] Worker error: {e}")
        active_downloads[job_id] = {
            'status': 'failed',
            'error': str(e),
            'timestamp': time.time()
        }


@app.route('/api/download', methods=['POST'])
@limiter.limit("10 per minute")
def download():
    """Start async media download."""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id')
    quality = data.get('quality', 'best')

    if not url:
        return jsonify({'success': False, 'error': 'Please provide a URL.'})

    # Validate URL (SSRF prevention)
    valid, error = validate_url(url)
    if not valid:
        return jsonify({'success': False, 'error': error})

    platform = detect_platform(url)
    if not platform:
        return jsonify({'success': False, 'error': 'Unsupported platform.'})

    logger.info(f"[Download] {platform} download requested from {get_client_ip()}")
    
    job_id = str(uuid.uuid4())
    active_downloads[job_id] = {
        'status': 'processing',
        'timestamp': time.time()
    }
    
    thread = threading.Thread(
        target=async_download_worker,
        args=(job_id, url, platform, format_id, quality, get_client_ip(), request.headers.get('User-Agent')),
        daemon=True
    )
    thread.start()

    return jsonify({'success': True, 'job_id': job_id})


@app.route('/api/download/status/<job_id>', methods=['GET'])
def download_status(job_id):
    """Check the status of an async download job."""
    job = active_downloads.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found or expired.'}), 404
    
    if job['status'] == 'completed':
        return jsonify({'success': True, 'status': 'completed', 'result': job['result']})
    elif job['status'] == 'failed':
        return jsonify({'success': False, 'status': 'failed', 'error': job['error']})
    else:
        return jsonify({'success': True, 'status': 'processing'})


@app.route('/api/file/<filename>')
def serve_file(filename):
    """Serve a downloaded file with path traversal protection."""
    # Sanitize filename — strip any directory components
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or '..' in filename:
        logger.warning(f"[Security] Path traversal attempt blocked: {filename} from {get_client_ip()}")
        return jsonify({'success': False, 'error': 'Invalid filename.'}), 400

    filepath = os.path.join(DOWNLOAD_DIR, safe_filename)

    # Verify the resolved path is actually inside DOWNLOAD_DIR
    real_path = os.path.realpath(filepath)
    real_download_dir = os.path.realpath(DOWNLOAD_DIR)
    if not real_path.startswith(real_download_dir):
        logger.warning(f"[Security] Directory escape attempt blocked from {get_client_ip()}")
        return jsonify({'success': False, 'error': 'Access denied.'}), 403

    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found.'}), 404

    @after_this_request
    def remove_file(response):
        """Schedule file for cleanup after serving."""
        # We don't remove immediately — let the cleanup thread handle it
        return response

    return send_file(
        filepath,
        as_attachment=True,
        download_name=safe_filename.split('_', 1)[-1] if '_' in safe_filename else safe_filename
    )


# ===================== ADMIN AUTHENTICATION =====================

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def admin_login():
    """Admin login page with rate limiting against brute-force."""
    if session.get('admin_authenticated'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            logger.info(f"[Admin] Login successful from {get_client_ip()}")
            return redirect(url_for('admin_dashboard'))
        else:
            logger.warning(f"[Admin] Failed login attempt from {get_client_ip()}")
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/admin/logout')
def admin_logout():
    """Admin logout."""
    session.pop('admin_authenticated', None)
    logger.info(f"[Admin] Logout from {get_client_ip()}")
    return redirect(url_for('index'))


# ===================== ADMIN DASHBOARD =====================

@app.route('/admin')
@require_admin
def admin_dashboard():
    """Serve the admin analytics dashboard (requires authentication)."""
    db.log_page_view(
        page='/admin',
        ip=get_client_ip(),
        user_agent=request.headers.get('User-Agent'),
        referrer=request.referrer
    )
    return render_template('admin.html')


@app.route('/api/stats/today')
@require_admin
def stats_today():
    """Get today's statistics."""
    return jsonify(db.get_stats_today())


@app.route('/api/stats/week')
@require_admin
def stats_week():
    """Get last 7 days statistics."""
    return jsonify(db.get_stats_range(7))


@app.route('/api/stats/month')
@require_admin
def stats_month():
    """Get last 30 days statistics."""
    return jsonify(db.get_stats_range(30))


@app.route('/api/stats/all')
@require_admin
def stats_all():
    """Get all-time statistics."""
    return jsonify(db.get_all_time_stats())


@app.route('/api/stats/recent')
@require_admin
def stats_recent():
    """Get recent downloads list."""
    return jsonify(db.get_recent_downloads(25))


# ===================== STARTUP =====================

if __name__ == '__main__':
    print("\n[*] Multi-Platform Media Downloader")
    print("=" * 45)
    print("[>] Instagram  | [>] YouTube")
    print("[>] Pinterest  | [>] Facebook")
    print("=" * 45)

    # Initialize database
    print("[*] Connecting to MySQL database...")
    if db.init_database():
        db.init_pool()
        print("[*] Database ready!")
    else:
        print("[!] Database connection failed!")
        print("[!] Make sure XAMPP MySQL is running.")
        print("[!] The app will work but downloads won't be tracked.\n")

    print("[*] Open http://localhost:5000 in your browser")
    print("[*] Admin dashboard: http://localhost:5000/admin")
    print(f"[*] Admin login: {ADMIN_USERNAME} / {'*' * len(ADMIN_PASSWORD)}\n")
    app.run(debug=True, host='0.0.0.0', port=5000)