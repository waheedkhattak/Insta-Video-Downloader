let currentInfo = null;

function switchTab(el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const platform = el.dataset.platform;
  const input = document.getElementById('urlInput');
  const placeholders = {
    all: 'Paste your video or image link here...',
    instagram: 'Paste Instagram Reel, Post, or Story link...',
    youtube: 'Paste YouTube video or Shorts link...',
    pinterest: 'Paste Pinterest pin link...',
    facebook: 'Paste Facebook video link...'
  };
  input.placeholder = placeholders[platform] || placeholders.all;
  input.focus();
}

async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    document.getElementById('urlInput').value = text;
    fetchInfo();
  } catch (err) {
    showStatus('Failed to read clipboard. Permissions may be denied.', 'error');
  }
}

function showStatus(msg, type) {
  const el = document.getElementById('status');
  if (type === 'loading') el.innerHTML = '<p class="loading"><i class="fas fa-spinner"></i> ' + msg + '</p>';
  else if (type === 'error') el.innerHTML = '<p class="error"><i class="fas fa-exclamation-circle"></i> ' + msg + '</p>';
  else el.innerHTML = '';
}

function formatDuration(sec) {
  if (!sec) return '';
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}

function formatViews(n) {
  if (!n) return '';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toString();
}

function formatBytes(b) {
  if (!b) return '';
  if (b >= 1e9) return (b / 1e9).toFixed(1) + ' GB';
  if (b >= 1e6) return (b / 1e6).toFixed(1) + ' MB';
  return (b / 1e3).toFixed(0) + ' KB';
}

async function fetchInfo() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) { showStatus('Please enter a URL', 'error'); return; }

  const btn = document.getElementById('fetchBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Fetching...';
  showStatus('Analyzing media...', 'loading');
  document.getElementById('resultSection').classList.add('hidden');

  try {
    const resp = await fetch('/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await resp.json();

    if (!data.success) {
      showStatus(data.error, 'error');
      return;
    }

    currentInfo = data;
    showStatus('', '');

    // Populate result card
    const thumb = document.getElementById('resultThumb');
    const vid = document.getElementById('resultVideo');
    const aud = document.getElementById('resultAudio');
    
    thumb.style.display = 'none';
    if(vid) { vid.style.display = 'none'; vid.src = ''; }
    if(aud) { aud.style.display = 'none'; aud.src = ''; }

    const proxyThumb = data.thumbnail ? '/api/proxy?url=' + encodeURIComponent(data.thumbnail) : '';

    if (data.stream_url && data.media_type === 'video') {
        if(vid) {
            // Proxy the video stream to bypass CORS
            vid.src = '/api/proxy?url=' + encodeURIComponent(data.stream_url);
            vid.poster = proxyThumb;
            vid.style.display = 'block';
            vid.onerror = function() {
                vid.style.display = 'none';
                if (proxyThumb) { thumb.src = proxyThumb; thumb.style.display = 'block'; }
            };
        }
    } else if (data.stream_url && data.media_type === 'audio') {
        if (proxyThumb) { thumb.src = proxyThumb; thumb.style.display = 'block'; }
        if(aud) {
            aud.src = data.stream_url;
            aud.style.display = 'block';
            aud.onerror = function() {
                aud.style.display = 'none';
            };
        }
    } else {
        if (proxyThumb) { thumb.src = proxyThumb; thumb.style.display = 'block'; }
    }

    document.getElementById('resultTitle').textContent = data.title;

    let metaHTML = '';
    if (data.platform) metaHTML += '<span><i class="fab fa-' + data.platform + '"></i> ' + data.platform.charAt(0).toUpperCase() + data.platform.slice(1) + '</span>';
    if (data.uploader && data.uploader !== 'Unknown') metaHTML += '<span><i class="fas fa-user"></i> ' + data.uploader + '</span>';
    if (data.duration) metaHTML += '<span><i class="fas fa-clock"></i> ' + formatDuration(data.duration) + '</span>';
    if (data.view_count) metaHTML += '<span><i class="fas fa-eye"></i> ' + formatViews(data.view_count) + ' views</span>';
    metaHTML += '<span><i class="fas fa-' + (data.media_type === 'image' ? 'image' : 'video') + '"></i> ' + data.media_type + '</span>';
    document.getElementById('resultMeta').innerHTML = metaHTML;

    // Formats
    const fmtSel = document.getElementById('formatSelector');
    const fmtSelect = document.getElementById('formatSelect');
    if (data.formats && data.formats.length > 0) {
      let options = data.formats.map(f =>
        '<option value="' + f.format_id + '">' + f.quality + (f.filesize ? ' (' + formatBytes(f.filesize) + ')' : '') + '</option>'
      ).join('');
      // Audio Only for YouTube
      if (data.media_type !== 'image' && data.platform === 'youtube') {
          options += '<option value="bestaudio">Audio Only (MP3)</option>';
      }
      fmtSelect.innerHTML = options;
      fmtSel.classList.remove('hidden');
    } else {
      fmtSel.classList.add('hidden');
    }

    document.getElementById('resultSection').classList.remove('hidden');

  } catch (e) {
    showStatus('Network error. Please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-search"></i> Fetch';
  }
}

async function downloadMedia() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) return;

  const btn = document.getElementById('downloadBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting download...';
  
  const progContainer = document.getElementById('progressContainer');
  const progBar = document.getElementById('progressBar');
  if(progContainer) {
      progContainer.style.display = 'block';
      progBar.style.width = '10%';
  }

  const fmtSelect = document.getElementById('formatSelect');
  const formatId = fmtSelect && !document.getElementById('formatSelector').classList.contains('hidden') ? fmtSelect.value : null;

  try {
    const resp = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, format_id: formatId })
    });
    const data = await resp.json();

    if (!data.success) {
      showStatus(data.error, 'error');
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-download"></i> Download';
      if(progContainer) progContainer.style.display = 'none';
      return;
    }

    const jobId = data.job_id;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing media...';
    if(progContainer) progBar.style.width = '40%';

    // Poll for status
    let pollCount = 0;
    const pollInterval = setInterval(async () => {
      pollCount++;
      if(progContainer && pollCount < 20) {
        progBar.style.width = (40 + pollCount * 2) + '%';
      }
      
      try {
        const statusResp = await fetch('/api/download/status/' + jobId);
        const statusData = await statusResp.json();

        if (!statusData.success || statusData.status === 'failed') {
          clearInterval(pollInterval);
          showStatus(statusData.error || 'Download failed', 'error');
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-download"></i> Download';
          if(progContainer) progContainer.style.display = 'none';
          return;
        }

        if (statusData.status === 'completed') {
          clearInterval(pollInterval);
          if(progContainer) progBar.style.width = '100%';
          
          // Trigger browser download
          const result = statusData.result;
          const a = document.createElement('a');
          a.href = '/api/file/' + encodeURIComponent(result.filename);
          a.download = result.title + '.' + result.ext;
          document.body.appendChild(a);
          a.click();
          a.remove();
          
          showStatus('Download complete!', 'success');
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-download"></i> Download';
          
          if(progContainer) setTimeout(() => progContainer.style.display = 'none', 1500);
          showPostDownloadAd();
        }
      } catch (e) {
        clearInterval(pollInterval);
        showStatus('Connection lost during download.', 'error');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> Download';
        if(progContainer) progContainer.style.display = 'none';
      }
    }, 2000);

  } catch (e) {
    showStatus('Download failed. Please try again.', 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-download"></i> Download';
    if(progContainer) progContainer.style.display = 'none';
  }
}

// Enter key support
const urlInput = document.getElementById('urlInput');
if (urlInput) {
  urlInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') fetchInfo();
  });
}

// ===================== THEME & QR =====================

function toggleTheme() {
  const body = document.body;
  const icon = document.querySelector('#themeToggle i');
  if (body.classList.contains('light-mode')) {
    body.classList.remove('light-mode');
    localStorage.setItem('theme', 'dark');
    if(icon) { icon.classList.remove('fa-sun'); icon.classList.add('fa-moon'); }
  } else {
    body.classList.add('light-mode');
    localStorage.setItem('theme', 'light');
    if(icon) { icon.classList.remove('fa-moon'); icon.classList.add('fa-sun'); }
  }
}

function generateQR() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) {
    showStatus('Please enter a URL first', 'error');
    return;
  }
  const container = document.getElementById('qrContainer');
  const img = document.getElementById('qrImage');
  
  if (container.style.display === 'block') {
    container.style.display = 'none';
    return;
  }
  
  // Using a free public QR code API
  img.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(window.location.origin + '?url=' + encodeURIComponent(url))}`;
  container.style.display = 'block';
}

// ===================== AD MANAGEMENT =====================

function initAds() {
  try {
    document.querySelectorAll('.adsbygoogle').forEach(() => {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    });
    setTimeout(() => {
      document.querySelectorAll('.ad-placeholder').forEach(el => {
        if (el.previousElementSibling && el.previousElementSibling.dataset.adStatus === 'filled') {
          el.style.display = 'none';
        }
      });
    }, 3000);
  } catch(e) {
    console.log('AdSense not loaded yet');
  }
}

function showPostDownloadAd() {
  const adZone3 = document.getElementById('adZone3');
  if (adZone3) {
    adZone3.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ===================== COOKIE CONSENT =====================

function acceptCookies() {
  localStorage.setItem('cookieConsent', 'accepted');
  const banner = document.getElementById('cookieBanner');
  if(banner) banner.style.display = 'none';
  initAds();
}

function declineCookies() {
  localStorage.setItem('cookieConsent', 'essential');
  const banner = document.getElementById('cookieBanner');
  if(banner) banner.style.display = 'none';
  document.querySelectorAll('.ad-container').forEach(el => el.style.display = 'none');
}

window.addEventListener('DOMContentLoaded', () => {
  const consent = localStorage.getItem('cookieConsent');
  const banner = document.getElementById('cookieBanner');
  if (consent === 'accepted') {
    if(banner) banner.style.display = 'none';
    initAds();
  } else if (consent === 'essential') {
    if(banner) banner.style.display = 'none';
    document.querySelectorAll('.ad-container').forEach(el => el.style.display = 'none');
  }
  
  // Theme initialization
  const theme = localStorage.getItem('theme');
  const icon = document.querySelector('#themeToggle i');
  if (theme === 'light') {
    document.body.classList.add('light-mode');
    if(icon) { icon.classList.remove('fa-moon'); icon.classList.add('fa-sun'); }
  }
  
  // Deep link check
  const urlParams = new URLSearchParams(window.location.search);
  const sharedUrl = urlParams.get('url');
  if(sharedUrl && urlInput) {
      urlInput.value = sharedUrl;
      setTimeout(fetchInfo, 500);
  }
});
