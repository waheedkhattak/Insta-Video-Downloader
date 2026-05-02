# Google AdSense Setup Guide for SaveMedia

## What Was Added

Your site now has **5 strategic ad zones** and full AdSense compliance features:

### Ad Placement Locations

| Zone | Location | Ad Format | Best For |
|------|----------|-----------|----------|
| **Zone 1** | Below hero section | Leaderboard (728x90) | High visibility on page load |
| **Zone 2** | Below URL input | Banner (responsive) | Users see it while waiting for results |
| **Zone 3** | Before features section | Rectangle (336x280) | Highest RPM zone |
| **Zone 4** | Between Features & How-to | Leaderboard (728x90) | Scroll-through impressions |
| **Zone 5** | Above footer | Banner (responsive) | Exit-intent impressions |

### Compliance Features Added
- Cookie consent banner (GDPR required for AdSense)
- Privacy Policy, Terms, Contact, DMCA footer links
- `ads.txt` file in `/static/` directory

---

## Step-by-Step: Get Approved & Start Earning

### Step 1: Deploy Your Site
You need a **live website with a custom domain** (e.g., `savemedia.com`). AdSense does NOT approve `localhost` or free subdomains.

**Recommended hosting options:**
- **Render.com** (free tier for Python/Flask)
- **Railway.app** ($5/mo)
- **DigitalOcean** ($4-6/mo)
- **Vercel** (with serverless functions)

### Step 2: Create AdSense Account
1. Go to [https://adsense.google.com](https://adsense.google.com)
2. Sign in with your Google account
3. Enter your website URL
4. Select your country and accept terms

### Step 3: Replace Placeholder IDs
Once approved, Google gives you a **Publisher ID** (e.g., `ca-pub-1234567890123456`).

Replace ALL instances of `ca-pub-XXXXXXXXXXXXXXXX` in these files:

**In `templates/index.html`** — find and replace:
```
ca-pub-XXXXXXXXXXXXXXXX  →  ca-pub-YOUR_ACTUAL_ID
```

Also replace each `AD_SLOT_X` with the actual ad unit slot IDs from your AdSense dashboard:
```
AD_SLOT_1  →  1234567890  (your Zone 1 slot)
AD_SLOT_2  →  2345678901  (your Zone 2 slot)
AD_SLOT_3  →  3456789012  (your Zone 3 slot)
AD_SLOT_4  →  4567890123  (your Zone 4 slot)
AD_SLOT_5  →  5678901234  (your Zone 5 slot)
```

**In `static/ads.txt`** — replace:
```
pub-XXXXXXXXXXXXXXXX  →  pub-YOUR_ACTUAL_ID
```

### Step 4: Create Ad Units in AdSense
1. Go to AdSense Dashboard → **Ads** → **By ad unit**
2. Create **5 ad units** (one for each zone):
   - Zone 1: Display ad → Horizontal
   - Zone 2: Display ad → Responsive
   - Zone 3: Display ad → Square/Rectangle
   - Zone 4: Display ad → Horizontal
   - Zone 5: Display ad → Responsive
3. Copy each ad unit's **slot ID** and replace in the HTML

### Step 5: Add Required Pages
Before AdSense approves you, create these pages (link them from footer):
- **Privacy Policy** — Use a generator like [privacypolicygenerator.info](https://www.privacypolicygenerator.info/)
- **Terms of Service**
- **Contact page** — A simple form or email
- **DMCA notice** — Important for a downloader site

---

## Earning Potential

| Traffic Level | Monthly Pageviews | Estimated Monthly Revenue |
|---------------|-------------------|--------------------------|
| Starting out | 1,000 - 5,000 | $2 - $15 |
| Growing | 10,000 - 50,000 | $30 - $150 |
| Established | 100,000 - 500,000 | $300 - $1,500 |
| Popular | 1,000,000+ | $3,000 - $10,000+ |

> [!TIP]
> Downloader sites typically earn **$2-5 RPM** (revenue per 1,000 pageviews) with AdSense. Traffic is the key — focus on SEO to grow!

---

## SEO Tips to Grow Traffic

1. Target keywords like "Instagram video downloader", "YouTube to MP4", "Pinterest image download"
2. Create blog content with how-to guides
3. Submit sitemap to Google Search Console
4. Get backlinks from tool listing sites

> [!IMPORTANT]
> Make sure your site has **original content** beyond just the tool. Google requires quality content for AdSense approval. Add a blog, FAQ section, or detailed how-to guides..
