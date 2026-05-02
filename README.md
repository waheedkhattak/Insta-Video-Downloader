# SaveMedia - Multi-Platform Media Downloader

A high-performance, production-ready web application built with Python (Flask) and `yt-dlp` that allows users to download media from various platforms including **Instagram, YouTube, Pinterest, and Facebook**.

## ✨ Features

- **Multi-Platform Support**: Download videos, images, Shorts, and Reels from major social platforms.
- **High Performance**: Asynchronous, non-blocking background downloads using Python threading.
- **Modern UI/UX**: Premium styling, Dark/Light mode toggle, animated progress bars, and clipboard paste support.
- **PWA Ready**: Can be installed natively on mobile and desktop devices.
- **QR Code Sharing**: Generate QR codes instantly for easy mobile-to-desktop sharing.
- **Admin Dashboard**: Secure, session-based dashboard to view real-time download statistics and page views.
- **Automated Analytics**: Built-in MySQL analytics tracking with an automated background thread that purges old records.
- **Monetization & SEO Ready**: Includes `robots.txt`, `sitemap.xml`, `ads.txt`, and mandatory legal pages (Privacy, Terms, DMCA, Contact).

## 🚀 Prerequisites

Before you begin, ensure you have the following installed:
- **Python 3.8+**
- **MySQL Server**
- **FFmpeg** (Required by `yt-dlp` for audio extraction and video merging)

## 🛠️ Setup Instructions

### 1. Clone the Repository
Ensure you are in the project directory.

### 2. Install Dependencies
Install the required Python packages using pip:
```bash
pip install -r requirements.txt
```

### 3. Database Setup
1. Open your MySQL client (e.g., phpMyAdmin, MySQL Workbench, or CLI).
2. Create a new database named `savemedia_db`.
3. Import the provided schema to create the necessary tables:
```bash
mysql -u root -p savemedia_db < database.sql
```

### 4. Configure Environment Variables
Rename or create a `.env` file in the root directory and add the following configuration:
```env
# Security
SECRET_KEY=change-this-to-a-random-secret-key-in-production

# Admin Dashboard Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=savemedia2026

# Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=savemedia_db
```

## 💻 Running the Application

Start the Flask development server:
```bash
python app.py
```

The application will be available at:
- **Frontend**: `http://127.0.0.1:5000`
- **Admin Dashboard**: `http://127.0.0.1:5000/admin`

## 🔒 Security Notes
- Ensure your `SECRET_KEY` and `ADMIN_PASSWORD` are changed before deploying to a live server.
- The app utilizes `Flask-Limiter` to protect the API endpoints from abuse.
- File serving is protected against Path Traversal, and URL fetching is protected against SSRF.

## 📄 License
This project is for personal use. Ensure you comply with the Terms of Service of the platforms you download media from.
