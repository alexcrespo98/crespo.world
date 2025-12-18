# Social Media Scrapers - Ubuntu Setup Guide

Complete guide for setting up and running Instagram, YouTube, and TikTok scrapers on Ubuntu with Google Drive integration.

## Important Note on Master Scraper

The master scraper provides a unified interface for selecting modes and platforms, but the individual scrapers (`instagram_scraper.py`, `youtube_scraper.py`, `tiktok_scraper.py`) retain their own interactive prompts. This design preserves the functionality and reliability of the individual scrapers while adding orchestration capabilities.

**What this means:**
- The master scraper handles mode selection (Normal, Custom, Deep, Test)
- Individual scrapers may still prompt for browser selection, confirmation, etc.
- This is by design to maintain scraper stability and avoid breaking changes

**Future Enhancement:** Individual scrapers could be refactored to accept mode parameters directly for full non-interactive operation.

## Table of Contents
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Google Drive Setup](#google-drive-setup)
- [Usage](#usage)
- [Master Scraper Modes](#master-scraper-modes)
- [Individual Scrapers](#individual-scrapers)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Ubuntu Packages

```bash
# Update package list
sudo apt update

# Install Python 3 and pip
sudo apt install python3 python3-pip

# Install Chrome/Chromium for Selenium
sudo apt install chromium-browser chromium-chromedriver

# OR install Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# Install Tesseract OCR (for TikTok scraper)
sudo apt install tesseract-ocr libtesseract-dev

# Install additional dependencies
sudo apt install curl wget git
```

### Python Packages

```bash
# Install required Python packages
pip3 install selenium pandas openpyxl requests pillow pytesseract

# OR use requirements file if available
pip3 install -r requirements.txt
```

### WebDriver Setup

The scrapers use Selenium WebDriver for Chrome. On Ubuntu, you can:

**Option 1: Use system ChromeDriver**
```bash
sudo apt install chromium-chromedriver
# Chromedriver will be at /usr/bin/chromedriver
```

**Option 2: Use webdriver-manager (automatic)**
```bash
pip3 install webdriver-manager
# This will automatically download and manage ChromeDriver
```

---

## Installation

### 1. Clone Repository

```bash
cd ~
git clone https://github.com/alexcrespo98/crespo.world.git
cd crespo.world/scrapers
```

### 2. Install Dependencies

```bash
# Install Python packages
pip3 install selenium pandas openpyxl requests pillow pytesseract webdriver-manager

# Verify installations
python3 -c "import selenium, pandas, pytesseract; print('✅ All packages installed')"
```

### 3. Verify Tesseract

```bash
# Check Tesseract installation
tesseract --version

# Test Tesseract
echo "Test" | tesseract stdin stdout
```

### 4. Test Chrome/Selenium

```bash
# Quick test
python3 -c "from selenium import webdriver; from selenium.webdriver.chrome.options import Options; opts = Options(); opts.add_argument('--headless'); driver = webdriver.Chrome(options=opts); driver.quit(); print('✅ Chrome/Selenium working')"
```

---

## Google Drive Setup

### Automated Setup (Recommended)

Run the setup script to install and configure rclone for Google Drive:

```bash
cd ~/crespo.world/scrapers
chmod +x setup_gdrive.sh
./setup_gdrive.sh
```

The script will:
1. Install rclone (if not present)
2. Guide you through Google Drive authentication
3. Create remote named 'gdrive'
4. Test upload permissions
5. Set up folder structure

### Manual Setup

If you prefer manual setup:

```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Configure Google Drive
rclone config

# Follow prompts:
# - Choose 'n' for new remote
# - Name it 'gdrive'
# - Choose 'drive' for Google Drive
# - Leave client_id and client_secret blank
# - Choose scope '1' for full access
# - Leave root_folder_id blank
# - Choose 'n' for advanced config
# - Choose 'y' for auto config (desktop) or 'n' (server)
# - Follow browser authentication
# - Choose 'n' for team drive
# - Confirm with 'y'

# Test configuration
rclone lsd gdrive:

# Create scrapers folder
rclone mkdir gdrive:scrapers

# Test upload
echo "test" > /tmp/test.txt
rclone copy /tmp/test.txt gdrive:scrapers/
rclone ls gdrive:scrapers/
```

### Verify Google Drive Setup

```bash
# List remotes (should show 'gdrive:')
rclone listremotes

# List Google Drive folders
rclone lsd gdrive:

# Test upload
echo "Test file" > /tmp/gdrive_test.txt
rclone copy /tmp/gdrive_test.txt gdrive:scrapers/

# Verify
rclone ls gdrive:scrapers/ | grep gdrive_test
```

---

## Usage

### Running the Master Scraper

The master scraper orchestrates all three platforms with various modes:

```bash
cd ~/crespo.world/scrapers
python3 master_scraper.py
```

You'll be prompted to select:
1. **Mode** (Normal, Custom, Deep, or Test)
2. **Platforms** (Instagram, YouTube, TikTok, or combination)

### Quick Start Examples

**Example 1: Normal scrape all platforms**
```bash
python3 master_scraper.py
# Select: 1 (Normal)
# Select: 1 (All platforms)
```

**Example 2: Test mode for Instagram only**
```bash
python3 master_scraper.py
# Select: 4 (Test)
# Select: n (not all platforms)
# Select: y for Instagram, n for others
```

**Example 3: Deep scrape with custom platforms**
```bash
python3 master_scraper.py
# Select: 3 (Deep)
# Select: y or n for all-time
# Select: 5 (Custom platforms)
# Choose which platforms
```

---

## Master Scraper Modes

### Mode 1: Normal Scrape (Default)

**What it does:**
- Instagram: 100 posts per account
- TikTok: 100 posts per account
- YouTube: ALL videos (fast, uses API)

**When to use:**
- Regular weekly/daily updates
- Balanced between speed and coverage
- Default recommended mode

**Example:**
```
Mode: 1 (Normal)
Platforms: All
Result: ~100 IG posts + ~100 TT posts + ALL YT videos
Time: ~30-60 minutes
```

---

### Mode 2: Custom Scrape

**What it does:**
- Lets you specify count for each platform separately
- Instagram: User-specified count
- TikTok: User-specified count
- YouTube: User-specified count or "all"

**When to use:**
- Need specific number of posts
- Different requirements per platform
- Testing specific date ranges

**Example:**
```
Mode: 2 (Custom)
Instagram: 50 posts
TikTok: 200 posts
YouTube: all
Result: 50 IG + 200 TT + ALL YT
Time: Varies by counts
```

---

### Mode 3: Deep Scrape

**What it does:**
- Instagram: 1 year back (default) or all-time
- TikTok: 1 year back (default) or all-time
- YouTube: ALL videos (same as normal)

**Options:**
- **1 year back**: Scrapes posts from last 365 days
- **All-time**: Scrapes ENTIRE history (can take hours)

**When to use:**
- Initial setup or major updates
- Need complete historical data
- Recovering from missed updates

**Example:**
```
Mode: 3 (Deep)
All-time: n (1 year)
Platforms: All
Result: 1yr IG + 1yr TT + ALL YT
Time: 1-3 hours

OR

Mode: 3 (Deep)
All-time: y
Platforms: All
Result: ALL IG + ALL TT + ALL YT
Time: 3-8 hours (depends on account sizes)
```

**⚠️ Warning:** All-time scrapes are resource-intensive and may trigger rate limits.

---

### Mode 4: Test Mode

**What it does:**
- Scrapes 30 posts from FIRST account only
- Tests each selected platform
- Displays results in terminal
- **Does NOT update Excel files**

**Features:**
- Platform selection (test all or choose specific)
- YouTube API quota warning
- Quick validation without modifying data

**When to use:**
- Testing scraper functionality
- Verifying credentials/setup
- Debugging issues
- Before major scrape operations

**Example:**
```
Mode: 4 (Test)
All platforms: n
Instagram: y
YouTube: n (avoid quota usage)
TikTok: y
Result: 30 IG posts + 30 TT posts (terminal only)
Time: ~5-10 minutes
Files: NO Excel updates
```

**⚠️ Important Notes:**
- Test mode uses API quota for YouTube
- Excel files are NOT modified
- Only tests first account of each platform
- Results displayed in terminal only

---

## Individual Scrapers

You can also run scrapers individually:

### Instagram Scraper

```bash
python3 instagram_scraper.py
```

**Features:**
- Scrapes Instagram Reels
- Multiple account support
- Hover + URL scraping methods
- Cross-validation and error detection

**Output:** `instagram_reels_analytics_tracker.xlsx`

---

### YouTube Scraper

```bash
python3 youtube_scraper.py
```

**Features:**
- Uses YouTube Data API v3
- Scrapes videos, shorts, and live streams
- Subscriber tracking
- API quota monitoring

**Requirements:**
- YouTube API key (included in script)
- API quota: ~10,000 units/day

**Output:** `youtube_analytics_tracker.xlsx`

---

### TikTok Scraper

```bash
python3 tiktok_scraper.py
```

**Features:**
- Uses yt-dlp for post data
- Screenshot scraping for stats
- Follower and like tracking
- Retry logic for failed scrapes

**Requirements:**
- Tesseract OCR
- Chrome/Chromium
- yt-dlp

**Output:** `tiktok_analytics_tracker.xlsx`

---

## Output Files

All scrapers create Excel files with the following structure:

### Excel File Format

```
instagram_reels_analytics_tracker.xlsx
├── Account1 (tab)
│   ├── Post ID
│   ├── URL
│   ├── Date
│   ├── Views
│   ├── Likes
│   ├── Comments
│   └── [Timestamp columns for each scrape]
├── Account2 (tab)
└── ...

youtube_analytics_tracker.xlsx
├── Channel1 (tab)
│   ├── Video ID
│   ├── Title
│   ├── Published Date
│   ├── Views
│   ├── Likes
│   ├── Comments
│   └── [Timestamp columns]
└── ...

tiktok_analytics_tracker.xlsx
├── Account1 (tab)
│   ├── Video ID
│   ├── Description
│   ├── Date
│   ├── Views
│   ├── Likes
│   ├── Comments
│   └── [Timestamp columns]
└── ...
```

### Google Drive Upload

If Google Drive is configured, files are automatically uploaded to:
```
Google Drive > scrapers/
├── instagram_reels_analytics_tracker.xlsx
├── youtube_analytics_tracker.xlsx
└── tiktok_analytics_tracker.xlsx
```

---

## Troubleshooting

### Common Issues

#### 1. Chrome/Selenium Issues

**Problem:** `selenium.common.exceptions.WebDriverException`

**Solution:**
```bash
# Update Chrome
sudo apt update
sudo apt upgrade chromium-browser

# OR reinstall ChromeDriver
sudo apt remove chromium-chromedriver
sudo apt install chromium-chromedriver

# Verify
chromium-browser --version
chromedriver --version
```

**Alternative:** Use webdriver-manager
```python
# Add to scraper imports
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# In setup_driver() or similar:
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
```

---

#### 2. Tesseract Not Found

**Problem:** `pytesseract.pytesseract.TesseractNotFound`

**Solution:**
```bash
# Install Tesseract
sudo apt install tesseract-ocr libtesseract-dev

# Verify installation
which tesseract
tesseract --version

# Test
echo "Hello" | tesseract stdin stdout
```

If still not working, check the path in `tiktok_scraper.py`:
```python
# Should be auto-detected on Ubuntu
# If not, manually set:
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
```

---

#### 3. Google Drive Upload Fails

**Problem:** `rclone not configured` or upload errors

**Solution:**
```bash
# Verify rclone installation
rclone version

# Check remotes
rclone listremotes

# Should show: gdrive:

# If not configured, run setup
./setup_gdrive.sh

# Or manual config
rclone config

# Test connection
rclone lsd gdrive:

# Test upload
echo "test" > /tmp/test.txt
rclone copy /tmp/test.txt gdrive:scrapers/
rclone ls gdrive:scrapers/
```

---

#### 4. Instagram Login Issues

**Problem:** Instagram blocks login or requires verification

**Solution:**
1. Update cookies in `instagram_scraper.py`:
   ```python
   INSTAGRAM_COOKIES = [
       {'name': 'sessionid', 'value': 'YOUR_SESSION_ID', ...},
       ...
   ]
   ```

2. Get cookies from browser:
   - Log into Instagram in Chrome
   - Open DevTools (F12) > Application > Cookies
   - Copy sessionid, csrftoken, etc.

3. Alternative: Use different account or proxy

---

#### 5. YouTube API Quota Exceeded

**Problem:** `quotaExceeded` error

**Solution:**
- Quota resets daily (midnight Pacific Time)
- Use test mode sparingly
- Consider deep scrape only weekly
- Monitor quota in Google Cloud Console

**Check quota usage:**
```python
# In youtube_scraper.py, the scraper tracks usage:
# Each channel lookup: ~3 units
# Each video list: ~100 units
# Daily limit: 10,000 units
```

---

#### 6. TikTok Scraper Timeout

**Problem:** Screenshots take too long or fail

**Solution:**
```bash
# Ensure stable internet connection
ping tokcount.com

# Clear Chrome cache
rm -rf ~/.cache/chromium/

# Try running with visible browser (remove headless)
# Edit tiktok_scraper.py temporarily:
# Comment out: chrome_options.add_argument("--headless")

# Check if tokcount.com is accessible
curl -I https://tokcount.com
```

---

#### 7. Permission Denied Errors

**Problem:** Can't write files or execute scripts

**Solution:**
```bash
# Make scripts executable
chmod +x master_scraper.py
chmod +x setup_gdrive.sh

# Check file permissions
ls -la

# Create temp directory if needed
mkdir -p ~/.tiktok_scraper_temp

# Ensure write access
touch test_file.xlsx
rm test_file.xlsx
```

---

#### 8. Module Import Errors

**Problem:** `ModuleNotFoundError: No module named 'X'`

**Solution:**
```bash
# Install missing packages
pip3 install selenium pandas openpyxl requests pillow pytesseract

# Verify installations
python3 -c "import selenium; import pandas; print('OK')"

# Check Python version
python3 --version  # Should be 3.7+

# Use virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

#### 9. Headless Mode Issues

**Problem:** Chrome crashes in headless mode

**Solution:**
```bash
# Add these arguments in scraper:
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')

# OR run with display (use Xvfb)
sudo apt install xvfb
xvfb-run python3 master_scraper.py
```

---

#### 10. Rate Limiting / Blocking

**Problem:** Scrapers get blocked or rate-limited

**Solution:**
- Add delays between requests
- Use rotating user agents
- Run at different times
- Use test mode to verify before full scrape
- Consider proxy/VPN for Instagram/TikTok

---

### Getting Help

If you encounter issues not covered here:

1. **Check logs:** Most scrapers print detailed error messages
2. **Run test mode:** Use Mode 4 to isolate issues
3. **Verify setup:** Run verification commands in each section
4. **Check accounts:** Ensure credentials/cookies are valid
5. **Update packages:** `sudo apt update && sudo apt upgrade`

---

## Performance Tips

### 1. Optimize Scraping Speed

```bash
# Use SSD for better I/O
# Close unnecessary apps
# Run during off-peak hours

# For large scrapes, consider:
nohup python3 master_scraper.py > scraper.log 2>&1 &
# This runs in background and logs output
```

### 2. Reduce Resource Usage

```python
# In scrapers, use headless mode (default)
chrome_options.add_argument('--headless')

# Disable images (faster)
chrome_options.add_argument('--blink-settings=imagesEnabled=false')

# Lower memory usage
chrome_options.add_argument('--disable-dev-shm-usage')
```

### 3. Schedule Regular Scrapes

```bash
# Note: Master scraper is currently interactive-only
# For automated scraping, run individual scrapers directly:

# Use cron for automated scraping
crontab -e

# Example (runs Instagram scraper every Monday at 2 AM):
# 0 2 * * 1 cd ~/crespo.world/scrapers && python3 instagram_scraper.py

# Example (runs all three scrapers sequentially):
# 0 2 * * 1 cd ~/crespo.world/scrapers && python3 instagram_scraper.py && python3 youtube_scraper.py && python3 tiktok_scraper.py

# View cron logs
grep CRON /var/log/syslog

# Alternative: For non-interactive master scraper, individual scrapers
# would need to be run with environment variables or config files
```

---

## Best Practices

### 1. Regular Updates
- Run Normal mode weekly for consistent data
- Use Deep mode monthly for comprehensive updates
- Test mode before major changes

### 2. Backup Data
```bash
# Backup Excel files
cp *.xlsx ~/backups/

# Backup to Google Drive (automatic if configured)
# Manual backup:
rclone sync . gdrive:scrapers/backup/
```

### 3. Monitor Quota
- YouTube: Check daily quota usage
- Avoid running multiple deep scrapes in one day
- Test mode counts toward quota

### 4. Error Handling
- Review error logs after scraping
- Address persistent errors promptly
- Keep credentials updated

---

## Additional Resources

### Documentation
- [Selenium Documentation](https://selenium-python.readthedocs.io/)
- [rclone Documentation](https://rclone.org/docs/)
- [YouTube API Reference](https://developers.google.com/youtube/v3)

### Tools
- [Chrome DevTools](https://developer.chrome.com/docs/devtools/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

### Analytics Dashboard
- View scraped data: https://crespo.world/crespomize.html

---

## Version History

- **v3.0** - Ubuntu compatibility, Google Drive integration, 4 scraper modes
- **v2.0** - Master scraper integration, interrupt handlers
- **v1.0** - Initial individual scrapers

---

## Support

For issues or questions:
1. Check this documentation first
2. Review error messages carefully
3. Test with Mode 4 (Test Mode)
4. Verify all dependencies are installed

---

**Last Updated:** 2024-12-18
