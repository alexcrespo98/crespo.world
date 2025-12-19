# Scraper System - Usage Guide

## Recent Updates

### 1. Bug Fixes
- **TikTok Scraper**: Fixed TypeError in `validate_data_before_upload` when sorting columns with mixed datetime/string types
- **Master Scraper**: Fixed import error (youtube_scrape → youtube_scraper)

### 2. Non-Interactive Mode

All scrapers now support non-interactive (automated) mode:

#### Master Scraper CLI Options
```bash
# Run all platforms in non-interactive mode with 100 posts each
python scrapers/master_scraper.py --non-interactive --platform all

# Run specific platform with custom post count
python scrapers/master_scraper.py --non-interactive --platform tiktok --posts 50

# Enable auto-retry for failed follower scrapes
python scrapers/master_scraper.py --non-interactive --auto-retry-followers

# Deep scrape mode (all posts)
python scrapers/master_scraper.py --non-interactive --mode deep
```

#### Scraper Parameters
Individual scrapers now accept these parameters:
- `max_posts`: Number of posts to scrape (default: 100)
- `auto_mode`: Skip all interactive prompts (default: False)
- `auto_retry`: Automatically retry failed follower scrapes (default: False)

Example:
```python
from tiktok_scraper import TikTokScraper

scraper = TikTokScraper()
scraper.run(max_posts=100, auto_mode=True, auto_retry=True)
```

### 3. Automated Daily Scraping

The new `auto_scraper.py` provides scheduled automation:

#### Features
- Runs daily at 6:00 AM
- Uses non-interactive mode with auto-retry
- Logs all output to `auto_scraper.log`
- PID file management to prevent multiple instances
- Platform-specific configuration:
  - Instagram: 100 posts
  - TikTok: 100 posts
  - YouTube: Deep scrape (all videos)

#### Usage

**Start the scheduler:**
```bash
python scrapers/auto_scraper.py --start
# or simply:
python scrapers/auto_scraper.py
```

**Stop the scheduler:**
```bash
python scrapers/auto_scraper.py --stop
```

**Check status:**
```bash
python scrapers/auto_scraper.py --status
```

**Run immediately (testing):**
```bash
python scrapers/auto_scraper.py --run-now
```

#### Configuration

Edit `auto_scraper.py` to customize:
```python
SCRAPE_CONFIG = {
    'instagram_posts': 100,      # Number of posts for Instagram
    'tiktok_posts': 100,          # Number of posts for TikTok
    'youtube_deep': True,         # Deep scrape YouTube (all videos)
    'auto_retry': True,           # Auto-retry failed follower scrapes
    'schedule_hour': 6,           # Hour to run (24-hour format)
    'schedule_minute': 0          # Minute to run
}
```

### 4. Requirements

Install APScheduler for automated scheduling:
```bash
pip install apscheduler
```

### 5. Data Validation

The TikTok scraper includes automatic data validation:
- Prevents uploading if new data has less than 90% of posts from previous scrape
- Validates before upload to Google Drive
- Threshold configurable via `DATA_VALIDATION_THRESHOLD` (default: 0.9)

## Migration Guide

### From Interactive to Non-Interactive Mode

**Before:**
```bash
python scrapers/master_scraper.py
# [user interaction required]
```

**After:**
```bash
python scrapers/master_scraper.py --non-interactive --platform all --auto-retry-followers
# Runs completely unattended
```

### Setting Up Automated Daily Scrapes

1. Install dependencies:
   ```bash
   pip install apscheduler
   ```

2. Test the scraper:
   ```bash
   python scrapers/auto_scraper.py --run-now
   ```

3. Start the scheduler:
   ```bash
   python scrapers/auto_scraper.py --start
   ```

4. For production, run as a background service:
   ```bash
   nohup python scrapers/auto_scraper.py --start > /dev/null 2>&1 &
   ```

## Troubleshooting

### Multiple Instances Running
```bash
# Check status
python scrapers/auto_scraper.py --status

# Stop if running
python scrapers/auto_scraper.py --stop

# Remove stale PID file if needed
rm scrapers/auto_scraper.pid
```

### View Logs
```bash
tail -f scrapers/auto_scraper.log
```

### Test Non-Interactive Mode
```bash
# Dry run to test configuration
python scrapers/master_scraper.py --non-interactive --platform tiktok --posts 10
```
