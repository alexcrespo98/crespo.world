#!/usr/bin/env python3
"""
YouTube Shorts/Videos Analytics Tracker v2.0
- NEW: Interrupt handler (Ctrl+C saves backup file)
- NEW: Master scraper integration support
- NEW: Early termination detection with recovery option
- NEW: Auto-detection when API quota is exhausted
- NEW: True subscriber count detection with web scraping and change polling
- Uses YouTube Data API v3 (official, free, reliable)
- Tracks multiple YouTube channels
- Configurable scrape modes: test, custom, deep (unlimited)
- Updates Excel with separate tabs per account
- Compatible with crespomize.html analytics dashboard
- Auto-uploads to Google Drive (when configured)
- Deep scrape now goes back as far as possible with pagination

True Subscriber Count Feature:
    After fetching the YouTube API subscriber count (which may be an estimate),
    the scraper queries a web endpoint to get the true/real-time subscriber count.
    It waits for any visual update if the count appears stale, polling until a
    change is observed or a timeout is reached. Terminal messages indicate when
    this process is happening and whether the real count was successfully retrieved.
"""

import sys
import subprocess
import os
from datetime import datetime, timedelta
import time
import requests
import json
import re
import signal
import traceback
from pathlib import Path

OUTPUT_EXCEL = "youtube_analytics_tracker.xlsx"

# YouTube channels to track
ACCOUNTS_TO_TRACK = [
    "popdartsgame",
    "bucketgolfgame",
    "playbattlegolf",
    "FlingGolf",
    "GolfPongGames",
    "DiscGOGames",
    "moonmediagames"
]

# YouTube API Key
API_KEY = "AIzaSyCj1JF5t2F_vonT8UUuEqdQAeWyjz5BOPE"

# Google Drive File ID (from your link)
GDRIVE_FILE_ID = "1yRLZpJLdaB9oPZtjcwIeJx-6q8lGF2dO"

class YoutubeScraper:
    def __init__(self):
        self.interrupted = False
        self.current_data = {}
        self.early_terminations = {}
        self.api_quota_used = 0
        self.api_quota_limit = 10000  # YouTube daily limit
        
        # Set up signal handler for interrupts
        signal.signal(signal.SIGINT, self.handle_interrupt)
        
    def handle_interrupt(self, signum, frame):
        """Handle Ctrl+C interrupt gracefully"""
        print("\n\n" + "="*70)
        print("⚠️  INTERRUPT DETECTED - SAVING BACKUP")
        print("="*70)
        self.interrupted = True
        
        # Save backup of current data
        if self.current_data:
            self.save_backup()
        
        print("\n✅ Backup saved. You can resume from where you left off.")
        sys.exit(0)
    
    def save_backup(self):
        """Save backup file with current progress"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"youtube_backup_{timestamp}.xlsx"
        
        try:
            import pandas as pd
            with pd.ExcelWriter(backup_name, engine='openpyxl') as writer:
                for username, df in self.current_data.items():
                    sheet_name = username[:31]
                    df.to_excel(writer, sheet_name=sheet_name)
            
            print(f"💾 Backup saved: {backup_name}")
            
            # Also save state file for resuming
            state = {
                'timestamp': timestamp,
                'accounts_completed': list(self.current_data.keys()),
                'early_terminations': self.early_terminations,
                'api_quota_used': self.api_quota_used
            }
            
            state_file = f"youtube_state_{timestamp}.json"
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"📋 State saved: {state_file}")
            
        except Exception as e:
            print(f"❌ Error saving backup: {e}")

    def install_package(self, package):
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

    def ensure_packages(self):
        packages_needed = []
        required = {
            'pandas': 'pandas',
            'openpyxl': 'openpyxl',
            'requests': 'requests',
            'selenium': 'selenium',
            'webdriver_manager': 'webdriver-manager'
        }
        for module, package in required.items():
            try:
                __import__(module)
            except ImportError:
                packages_needed.append(package)
        if packages_needed:
            print("📦 Installing required packages...")
            for p in packages_needed:
                self.install_package(p)
            print("✅ All packages installed!")

    def check_api_quota(self, response):
        """Check if API quota is exhausted"""
        if response.status_code == 403:
            data = response.json()
            if 'error' in data:
                error_msg = data['error'].get('message', '')
                if 'quota' in error_msg.lower():
                    return True, "API quota exceeded"
        return False, None

    def track_api_usage(self, endpoint_type='search'):
        """Track API quota usage"""
        # Approximate quota costs
        costs = {
            'search': 100,
            'channels': 1,
            'videos': 1,
            'playlistItems': 1
        }
        self.api_quota_used += costs.get(endpoint_type, 1)
        
        if self.api_quota_used > self.api_quota_limit * 0.8:
            print(f"  ⚠️ API quota warning: {self.api_quota_used}/{self.api_quota_limit} units used")

    def get_livecounts_subscriber_count(self, channel_id, max_wait_seconds=15, stability_threshold=3):
        """
        Get exact subscriber count from livecounts.io using stable value detection.
        
        This method loads the livecounts.io page for the channel and waits for the
        odometer value to stabilize (stop changing) before capturing it.
        
        Args:
            channel_id: The YouTube channel ID (e.g., 'UCo4RsSblLnfBG5IuHJsvj4g')
            max_wait_seconds: Maximum time to wait for stable value (default 15s)
            stability_threshold: Seconds the value must remain stable (default 3s)
            
        Returns:
            int or None: The exact subscriber count, or None if unable to fetch
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager
            
            url = f"https://livecounts.io/youtube-live-subscriber-counter/{channel_id}"
            
            # Set up headless Chrome
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--disable-logging")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            try:
                driver.get(url)
                time.sleep(2)  # Initial wait for page load
                
                last_value = None
                stable_since = None
                start_time = time.time()
                
                while time.time() - start_time < max_wait_seconds:
                    current_value = None
                    
                    try:
                        # Try multiple selectors to find the odometer value
                        selectors = [
                            ".odometer-inside",
                            "[class*='odometer']",
                            "[class*='count']"
                        ]
                        
                        for selector in selectors:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                text = elements[0].text.strip().replace(' ', '').replace(',', '')
                                # Extract just digits
                                digits = ''.join(c for c in text if c.isdigit())
                                if digits:
                                    current_value = int(digits)
                                    break
                    except Exception:
                        pass
                    
                    if current_value:
                        if current_value == last_value:
                            if stable_since is None:
                                stable_since = time.time()
                            
                            stability_duration = time.time() - stable_since
                            if stability_duration >= stability_threshold:
                                # Value has been stable long enough
                                return current_value
                        else:
                            # Value changed, reset stability timer
                            stable_since = None
                            last_value = current_value
                    
                    time.sleep(0.5)
                
                # Max wait reached, return last value if we have one
                return last_value
                
            finally:
                driver.quit()
                
        except Exception as e:
            # Log error but don't crash - we'll fall back to other methods
            error_msg = str(e)
            # Show more context for debugging but keep it readable
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            print(f"  ⚠️ LiveCounts fetch failed: {error_msg}")
            return None

    def get_web_subscriber_count(self, channel_id):
        """
        Fetch the true subscriber count from YouTube's web endpoint.
        
        This queries the YouTube channel page to get the real-time subscriber
        count rather than the rounded/estimated value from the API.
        
        Args:
            channel_id: The YouTube channel ID
            
        Returns:
            int or None: The true subscriber count, or None if unable to fetch
        """
        try:
            # Use YouTube's channel page to scrape the real subscriber count
            url = f"https://www.youtube.com/channel/{channel_id}"
            headers = {
                # Use a generic User-Agent that represents a standard browser request
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                return None
            
            html_content = response.text
            
            # Try to extract subscriber count from the page content
            # YouTube embeds data in ytInitialData JSON
            match = re.search(r'"subscriberCountText":\s*\{\s*"accessibility":\s*\{\s*"accessibilityData":\s*\{\s*"label":\s*"([^"]+)"', html_content)
            if match:
                subscriber_text = match.group(1)
                # Parse the subscriber count from text like "1.23 million subscribers"
                count = self._parse_subscriber_text(subscriber_text)
                if count:
                    return count
            
            # Alternative pattern for simpleText
            match = re.search(r'"subscriberCountText":\s*\{\s*"simpleText":\s*"([^"]+)"', html_content)
            if match:
                subscriber_text = match.group(1)
                count = self._parse_subscriber_text(subscriber_text)
                if count:
                    return count
            
            return None
            
        except requests.RequestException:
            # Network or HTTP errors when fetching the page
            return None
        except (ValueError, TypeError):
            # Errors during parsing or data extraction
            return None

    def _parse_subscriber_text(self, text):
        """
        Parse subscriber count from text like "1.23M subscribers" or "1,234 subscribers"
        
        Args:
            text: The subscriber count text from YouTube
            
        Returns:
            int or None: The parsed subscriber count
        """
        try:
            # Remove "subscribers" suffix and clean up
            text = text.lower().replace('subscribers', '').replace('subscriber', '').strip()
            
            # Handle full words first (billion, million), then abbreviations (K, M, B)
            multiplier = 1
            if 'billion' in text:
                multiplier = 1000000000
                text = text.replace('billion', '')
            elif 'million' in text:
                multiplier = 1000000
                text = text.replace('million', '')
            elif 'b' in text:
                multiplier = 1000000000
                text = text.replace('b', '')
            elif 'm' in text:
                multiplier = 1000000
                text = text.replace('m', '')
            elif 'k' in text:
                multiplier = 1000
                text = text.replace('k', '')
            
            # Remove commas and parse
            text = text.replace(',', '').replace(' ', '').strip()
            
            if text:
                count = float(text) * multiplier
                return int(count)
            
            return None
            
        except ValueError:
            # Raised when float() fails to parse the text
            return None

    def wait_for_subscriber_count_update(self, channel_id, api_count, max_wait_seconds=10, poll_interval=2):
        """
        Get the true/exact subscriber count using livecounts.io as the primary source.
        
        This method first tries livecounts.io which provides exact subscriber counts
        using the stable value detection approach. If that fails, it falls back to
        YouTube's web endpoint.
        
        Args:
            channel_id: The YouTube channel ID
            api_count: The subscriber count from the YouTube API (used as reference)
            max_wait_seconds: Maximum time to wait for an update (default 10 seconds)
            poll_interval: Time between polling attempts (default 2 seconds)
            
        Returns:
            dict: Contains 'count' (the final subscriber count), 'is_updated' (bool),
                  and 'source' (description of where the count came from)
        """
        print(f"  🔄 Fetching exact subscriber count from LiveCounts.io...")
        
        # Try livecounts.io up to 2 times if we get suspicious values
        max_livecounts_attempts = 2
        for attempt in range(max_livecounts_attempts):
            livecounts_value = self.get_livecounts_subscriber_count(channel_id)
            
            if livecounts_value is not None:
                # Validate the LiveCounts value
                is_valid = True
                rejection_reason = None
                
                # Check 1: Value is ridiculously large compared to API estimate
                # If LiveCounts is more than 100x the API estimate, it's likely a scraping error
                if api_count > 0 and livecounts_value > api_count * 100:
                    is_valid = False
                    rejection_reason = f"value {livecounts_value:,} is >100x API estimate {api_count:,}"
                
                # Check 2: Value ends with "00" (same as rounded API value)
                # This suggests LiveCounts may have returned a rounded value, not exact
                elif livecounts_value == api_count and api_count % 100 == 0:
                    is_valid = False
                    rejection_reason = f"value {livecounts_value:,} matches rounded API estimate"
                
                # Check 3: Value is unreasonably small (less than 1% of API estimate)
                elif api_count > 1000 and livecounts_value < api_count * 0.01:
                    is_valid = False
                    rejection_reason = f"value {livecounts_value:,} is <1% of API estimate {api_count:,}"
                
                if is_valid:
                    print(f"  ✅ LiveCounts exact count: {livecounts_value:,} (API estimate: {api_count:,})")
                    return {
                        'count': livecounts_value,
                        'is_updated': True,
                        'source': 'LiveCounts.io (exact)'
                    }
                else:
                    if attempt < max_livecounts_attempts - 1:
                        print(f"  ⚠️ LiveCounts returned suspicious value: {rejection_reason}")
                        print(f"  🔄 Retrying LiveCounts ({attempt + 2}/{max_livecounts_attempts})...")
                    else:
                        print(f"  ⚠️ LiveCounts failed validation: {rejection_reason}")
        
        # Fallback to YouTube web scraping
        print(f"  ⚠️ LiveCounts failed, trying YouTube web fallback...")
        
        initial_web_count = self.get_web_subscriber_count(channel_id)
        
        if initial_web_count is None:
            print(f"  ⚠️ Web fallback also failed, using API value")
            return {
                'count': api_count,
                'is_updated': False,
                'source': 'API (all methods failed)'
            }
        
        print(f"  📊 Web fallback count: {initial_web_count:,} (API: {api_count:,})")
        
        # If the web count differs significantly from API, it might already be accurate
        # Wait and poll to see if it changes (indicating a stale cache refresh)
        start_time = time.time()
        previous_count = initial_web_count
        
        print(f"  ⏳ Waiting for subscriber count to refresh (max {max_wait_seconds}s)...")
        
        while time.time() - start_time < max_wait_seconds:
            time.sleep(poll_interval)
            
            current_count = self.get_web_subscriber_count(channel_id)
            
            if current_count is None:
                continue
            
            if current_count != previous_count:
                print(f"  ✅ Subscriber count updated: {previous_count:,} → {current_count:,}")
                return {
                    'count': current_count,
                    'is_updated': True,
                    'source': 'Web (live update detected)'
                }
            
            previous_count = current_count
            elapsed = time.time() - start_time
            remaining = max_wait_seconds - elapsed
            if remaining > 0:
                print(f"  ⏳ Still waiting... ({remaining:.0f}s remaining)")
        
        # Timeout reached, use the last fetched web count
        if initial_web_count != api_count:
            print(f"  ℹ️ Timeout reached. Using web count: {initial_web_count:,} (differs from API: {api_count:,})")
            return {
                'count': initial_web_count,
                'is_updated': False,
                'source': 'Web (no live update, but differs from API)'
            }
        else:
            print(f"  ℹ️ Timeout reached. Web and API counts match: {api_count:,}")
            return {
                'count': api_count,
                'is_updated': False,
                'source': 'API/Web (counts match)'
            }

    def get_channel_info(self, channel_name):
        """
        Get channel ID, statistics, and uploads playlist.
        
        After fetching the YouTube API subscriber count (which may be an estimate),
        this method queries the web endpoint to get the true/real-time subscriber
        count. It waits for any visual update if the count appears stale, polling
        until a change is observed or a timeout is reached.
        
        Args:
            channel_name: The YouTube channel handle or name
            
        Returns:
            dict or None: Channel information including true subscriber count,
                          or None if the channel cannot be found
        """
        # Try by handle first
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id,snippet,statistics,contentDetails',
            'forHandle': channel_name,
            'key': API_KEY
        }
        
        response = requests.get(url, params=params)
        self.track_api_usage('channels')
        
        # Check for quota exhaustion
        quota_exceeded, msg = self.check_api_quota(response)
        if quota_exceeded:
            print(f"  ❌ {msg}")
            return None
        
        data = response.json()
        
        if 'items' in data and len(data['items']) > 0:
            item = data['items'][0]
            channel_id = item['id']
            api_subscribers = int(item['statistics'].get('subscriberCount', 0))
            
            # Get true subscriber count using web scraping with polling
            subscriber_result = self.wait_for_subscriber_count_update(
                channel_id, api_subscribers
            )
            
            return {
                'channel_id': channel_id,
                'title': item['snippet']['title'],
                'subscribers': subscriber_result['count'],
                'subscribers_source': subscriber_result['source'],
                'subscribers_api': api_subscribers,
                'total_views': int(item['statistics'].get('viewCount', 0)),
                'total_videos': int(item['statistics'].get('videoCount', 0)),
                'uploads_playlist': item['contentDetails']['relatedPlaylists']['uploads']
            }
        
        # Try search if handle doesn't work
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            'part': 'snippet',
            'q': channel_name,
            'type': 'channel',
            'key': API_KEY,
            'maxResults': 1
        }
        
        response = requests.get(url, params=params)
        self.track_api_usage('search')
        
        quota_exceeded, msg = self.check_api_quota(response)
        if quota_exceeded:
            print(f"  ❌ {msg}")
            return None
        
        data = response.json()
        
        if 'items' in data and len(data['items']) > 0:
            channel_id = data['items'][0]['snippet']['channelId']
            
            # Get full details
            url = "https://www.googleapis.com/youtube/v3/channels"
            params = {
                'part': 'id,snippet,statistics,contentDetails',
                'id': channel_id,
                'key': API_KEY
            }
            
            response = requests.get(url, params=params)
            self.track_api_usage('channels')
            
            data = response.json()
            
            if 'items' in data:
                item = data['items'][0]
                api_subscribers = int(item['statistics'].get('subscriberCount', 0))
                
                # Get true subscriber count using web scraping with polling
                subscriber_result = self.wait_for_subscriber_count_update(
                    channel_id, api_subscribers
                )
                
                return {
                    'channel_id': item['id'],
                    'title': item['snippet']['title'],
                    'subscribers': subscriber_result['count'],
                    'subscribers_source': subscriber_result['source'],
                    'subscribers_api': api_subscribers,
                    'total_views': int(item['statistics'].get('viewCount', 0)),
                    'total_videos': int(item['statistics'].get('videoCount', 0)),
                    'uploads_playlist': item['contentDetails']['relatedPlaylists']['uploads']
                }
        
        return None

    def get_all_videos_paginated(self, channel_info, channel_name, max_videos=None, deep_scrape=False):
        """Get videos with pagination support for deep scraping"""
        uploads_playlist = channel_info['uploads_playlist']
        all_video_ids = []
        page_token = None
        page_count = 0
        early_termination = None
        
        # For deep scrape, we'll keep going until we run out of videos
        target_videos = 999999 if deep_scrape else (max_videos or 30)
        
        print(f"  📹 Fetching video list{'... (unlimited deep scrape)' if deep_scrape else f' (target: {target_videos})'}...")
        
        while len(all_video_ids) < target_videos:
            url = "https://www.googleapis.com/youtube/v3/playlistItems"
            params = {
                'part': 'contentDetails',
                'playlistId': uploads_playlist,
                'maxResults': 50,  # Maximum allowed per request
                'key': API_KEY
            }
            
            if page_token:
                params['pageToken'] = page_token
            
            response = requests.get(url, params=params)
            self.track_api_usage('playlistItems')
            
            # Check for quota exhaustion
            quota_exceeded, msg = self.check_api_quota(response)
            if quota_exceeded:
                print(f"  ⚠️ {msg} - saving progress")
                early_termination = {
                    'reason': 'quota_exceeded',
                    'videos_scraped': len(all_video_ids),
                    'message': msg
                }
                self.early_terminations[channel_name] = early_termination
                break
            
            data = response.json()
            
            if 'error' in data:
                print(f"  ⚠️ API Error: {data['error'].get('message', 'Unknown error')}")
                early_termination = {
                    'reason': 'api_error',
                    'videos_scraped': len(all_video_ids),
                    'message': data['error'].get('message', 'Unknown error')
                }
                self.early_terminations[channel_name] = early_termination
                break
            
            if 'items' in data:
                video_ids = [item['contentDetails']['videoId'] for item in data['items']]
                all_video_ids.extend(video_ids)
                page_count += 1
                
                # Progress update for deep scrape
                if deep_scrape and page_count % 5 == 0:
                    print(f"    Progress: {len(all_video_ids)} videos fetched...")
            
            # Check if there are more pages
            page_token = data.get('nextPageToken')
            if not page_token:
                print(f"    ✅ Reached end of channel - {len(all_video_ids)} total videos found")
                break
            
            # If not deep scraping and we have enough videos, stop
            if not deep_scrape and len(all_video_ids) >= target_videos:
                all_video_ids = all_video_ids[:target_videos]
                break
        
        return all_video_ids, early_termination

    def get_video_details_batch(self, video_ids, channel_name):
        """Get full details for a batch of videos (max 50 at a time)"""
        if not video_ids:
            return []
        
        all_videos = []
        
        # Process in batches of 50 (API limit)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                'part': 'snippet,statistics,contentDetails',
                'id': ','.join(batch),
                'key': API_KEY
            }
            
            response = requests.get(url, params=params)
            self.track_api_usage('videos')
            
            # Check for quota exhaustion
            quota_exceeded, msg = self.check_api_quota(response)
            if quota_exceeded:
                print(f"  ⚠️ {msg} - returning partial data")
                self.early_terminations[channel_name] = {
                    'reason': 'quota_exceeded',
                    'videos_scraped': len(all_videos),
                    'message': msg
                }
                return all_videos
            
            data = response.json()
            
            if 'items' in data:
                for item in data['items']:
                    # Parse duration
                    duration = item['contentDetails']['duration']
                    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
                    if match:
                        hours = int(match.group(1) or 0)
                        minutes = int(match.group(2) or 0)
                        seconds = int(match.group(3) or 0)
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                    else:
                        total_seconds = 0
                    
                    # Determine if it's a Short
                    is_short = total_seconds <= 60
                    
                    stats = item['statistics']
                    snippet = item['snippet']
                    
                    # Parse published date
                    published_str = snippet['publishedAt']
                    published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    
                    all_videos.append({
                        'video_id': item['id'],
                        'title': snippet['title'],
                        'date': published_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'date_display': published_date.strftime('%b %d, %Y'),
                        'date_timestamp': published_date,
                        'duration': total_seconds,
                        'is_short': is_short,
                        'views': int(stats.get('viewCount', 0)),
                        'likes': int(stats.get('likeCount', 0)),
                        'comments': int(stats.get('commentCount', 0)),
                        'favorites': int(stats.get('favoriteCount', 0))
                    })
            
            # Show progress for large batches
            if len(video_ids) > 100 and (i + 50) % 100 == 0:
                print(f"    Processing details: {min(i + 50, len(video_ids))}/{len(video_ids)} videos...")
        
        return all_videos

    def scrape_youtube_channel(self, channel_name, max_videos=30, deep_scrape=False, test_mode=False):
        """Scrape a single YouTube channel"""
        print(f"  📺 Getting channel info...")
        channel_info = self.get_channel_info(channel_name)
        
        if not channel_info:
            print(f"  ❌ Channel not found or API issue: {channel_name}")
            return [], None, None
        
        print(f"  ✅ Found: {channel_info['title']}")
        print(f"  👥 Subscribers: {channel_info['subscribers']:,}")
        print(f"  📊 Total channel videos: {channel_info['total_videos']:,}")
        
        # Get video IDs with pagination
        video_ids, early_termination = self.get_all_videos_paginated(
            channel_info, channel_name, max_videos, deep_scrape
        )
        
        if not video_ids:
            print(f"  ⚠️ No videos found")
            return [], channel_info['subscribers'], channel_info.get('total_views', 0)
        
        # Get detailed video info
        print(f"  📊 Getting detailed stats for {len(video_ids)} videos...")
        videos = self.get_video_details_batch(video_ids, channel_name)
        
        # Calculate engagement rates
        for video in videos:
            if video['views'] > 0:
                engagement = ((video['likes'] + video['comments']) / video['views']) * 100
                video['engagement'] = round(engagement, 2)
            else:
                video['engagement'] = 0
        
        # Sort by date (newest first)
        videos.sort(key=lambda x: x['date'], reverse=True)
        
        # For deep scrape, show date range
        if deep_scrape and videos:
            oldest_date = datetime.strptime(videos[-1]['date'], '%Y-%m-%d %H:%M:%S')
            newest_date = datetime.strptime(videos[0]['date'], '%Y-%m-%d %H:%M:%S')
            days_span = (newest_date - oldest_date).days
            print(f"  📅 Date range: {videos[-1]['date_display']} to {videos[0]['date_display']} ({days_span} days)")
        
        if test_mode:
            print(f"\n  📋 Videos scraped:")
            for i, video in enumerate(videos[:10], 1):
                video_type = "SHORT" if video['is_short'] else "VIDEO"
                print(f"    {i}. [{video_type}] {video['title'][:50]}...")
                print(f"       Date: {video['date_display']}")
                print(f"       Views: {video['views']:,}, Likes: {video['likes']:,}")
                print(f"       Engagement: {video['engagement']}%")
        
        # Calculate total likes across all videos
        total_likes = sum(v['likes'] for v in videos)
        
        # Count shorts vs regular videos
        shorts_count = sum(1 for v in videos if v.get('is_short', False))
        print(f"  📱 Content breakdown: {shorts_count} Shorts, {len(videos) - shorts_count} regular videos")
        
        return videos, channel_info['subscribers'], total_likes

    def load_existing_excel(self):
        """Load existing Excel file"""
        import pandas as pd
        if os.path.exists(OUTPUT_EXCEL):
            try:
                excel_data = pd.read_excel(OUTPUT_EXCEL, sheet_name=None, index_col=0)
                return excel_data
            except:
                return {}
        return {}

    def create_dataframe_for_account(self, videos_data, subscribers, total_likes, timestamp_col, existing_df=None):
        """Create or update DataFrame for YouTube channel"""
        import pandas as pd
        
        if existing_df is not None and not existing_df.empty:
            df = existing_df.copy()
        else:
            df = pd.DataFrame()
        
        # Add timestamp column if it doesn't exist
        if timestamp_col not in df.columns:
            df[timestamp_col] = None
        
        # Add channel-level metrics
        df.loc["followers", timestamp_col] = subscribers
        df.loc["total_likes", timestamp_col] = total_likes
        df.loc["posts_scraped", timestamp_col] = len(videos_data)
        
        # Add per-video metrics
        for video in videos_data:
            video_id = video['video_id']
            
            metrics = {
                'Date': video['date'],
                'Views': video['views'],
                'Likes': video['likes'],
                'Comments': video['comments'],
                'Shares': 0,  # YouTube doesn't provide share count
                'EngagementRate': video['engagement']
            }
            
            for metric_name, value in metrics.items():
                row_name = f"post_{video_id}_{metric_name}"
                if row_name not in df.index:
                    df.loc[row_name] = None
                df.loc[row_name, timestamp_col] = value
        
        return df

    def save_to_excel(self, all_account_data):
        """Save all account data to Excel"""
        import pandas as pd
        with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
            for username, df in all_account_data.items():
                sheet_name = username[:31]
                df.to_excel(writer, sheet_name=sheet_name)
        print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")

    def upload_to_google_drive(self):
        """Upload to Google Drive if configured"""
        print("\n" + "="*70)
        print("☁️  Uploading to Google Drive...")
        print("="*70)
        
        try:
            result = subprocess.run(['rclone', 'version'], 
                capture_output=True, 
                text=True)
            if result.returncode != 0:
                raise FileNotFoundError
            
            excel_path = os.path.abspath(OUTPUT_EXCEL)
            print(f"\n📤 Attempting to upload {OUTPUT_EXCEL}...")
            
            upload_result = subprocess.run(
                ['rclone', 'copy', excel_path, 'gdrive:', '--update', '-v'],
                capture_output=True,
                text=True
            )
            
            if upload_result.returncode == 0:
                print("✅ Successfully uploaded to Google Drive!")
                print(f"📁 File ID: {GDRIVE_FILE_ID}")
                print("🌐 View at: https://crespo.world/crespomize.html")
                return True
            else:
                print(f"⚠️ Upload issue: {upload_result.stderr}")
                return False
                
        except FileNotFoundError:
            print("⚠️ rclone not found - Google Drive upload skipped")
            return False
        except Exception as e:
            print(f"⚠️ Upload error: {e}")
            return False

    def handle_early_terminations(self, all_account_data, timestamp_col):
        """Handle channels that were cut off early"""
        if not self.early_terminations:
            return
        
        print("\n" + "="*70)
        print("⚠️  EARLY TERMINATION DETECTED")
        print("="*70)
        
        for channel, termination_info in self.early_terminations.items():
            print(f"\n@{channel}:")
            print(f"  Reason: {termination_info['reason'].replace('_', ' ').title()}")
            print(f"  Videos scraped: {termination_info['videos_scraped']}")
            if 'message' in termination_info:
                print(f"  Message: {termination_info['message']}")
        
        if 'quota_exceeded' in str(self.early_terminations.values()):
            print("\n⚠️ API quota exceeded. YouTube allows 10,000 units per day.")
            print("   Try again tomorrow or use a different API key.")
            return
        
        retry = input("\n🔄 Would you like to try to get more videos from these channels? (y/n): ").strip().lower()
        
        if retry == 'y':
            print("\n🔄 Attempting to get more videos...")
            for channel in self.early_terminations.keys():
                print(f"\n📺 Re-attempting @{channel}...")
                try:
                    videos_data, subscribers, total_likes = self.scrape_youtube_channel(
                        channel, 
                        max_videos=2000,
                        deep_scrape=True,
                        test_mode=False
                    )
                    
                    if len(videos_data) > self.early_terminations[channel]['videos_scraped']:
                        print(f"  ✅ Got {len(videos_data) - self.early_terminations[channel]['videos_scraped']} additional videos!")
                        existing_df = all_account_data.get(channel)
                        df = self.create_dataframe_for_account(
                            videos_data, subscribers, total_likes, timestamp_col, existing_df
                        )
                        all_account_data[channel] = df
                    else:
                        print(f"  ℹ️  No additional videos found")
                except Exception as e:
                    print(f"  ❌ Re-attempt failed: {e}")

    def get_scrape_mode(self):
        """Get scraping mode from user"""
        print("\n" + "="*70)
        print("🎯 SELECT SCRAPE MODE")
        print("="*70)
        print("\n1. Custom number of videos (default: 30)")
        print("2. Deep scrape (ALL videos - no limit)")
        print("3. Test mode (10 videos on first channel only)")
        print()
        
        while True:
            choice = input("Enter your choice (1, 2, or 3, default=1): ").strip()
            
            if choice == '1' or choice == '':
                num_input = input("\nHow many videos per channel? (default 30): ").strip()
                try:
                    num_videos = int(num_input) if num_input else 30
                    if num_videos > 0:
                        return num_videos, False, False
                    else:
                        print("Please enter a positive number.")
                except ValueError:
                    print("Invalid input. Using default: 30")
                    return 30, False, False
                    
            elif choice == '2':
                confirm = input("\n⚠️ Deep scrape will fetch ALL videos. This may use significant API quota. Continue? (y/n): ").strip().lower()
                if confirm == 'y':
                    return None, True, False
                    
            elif choice == '3':
                return 10, False, True
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def run(self, max_posts=None, auto_mode=False, auto_retry=False):
        """Main execution function"""
        import pandas as pd
        
        self.ensure_packages()
        
        print("\n" + "="*70)
        print("🎬 YouTube Analytics Tracker v2.0")
        print("="*70)
        
        # Test API key
        print("\n🔑 Testing API key...")
        test_url = f"https://www.googleapis.com/youtube/v3/channels?part=id&forHandle=popdartsgame&key={API_KEY}"
        try:
            test_response = requests.get(test_url)
            if test_response.status_code == 200:
                print("✅ API key is valid!")
                self.track_api_usage('channels')
            else:
                print(f"❌ API key error: {test_response.json()}")
                print("\nPlease check your API key in the script")
                return
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return
        
        # Get scrape mode
        if auto_mode:
            max_videos = max_posts if max_posts else 100
            deep_scrape = max_posts is None  # Deep scrape if no max_posts specified in auto mode
            test_mode = False
        else:
            max_videos, deep_scrape, test_mode = self.get_scrape_mode()
        
        # Set up accounts to scrape
        if test_mode:
            print("\n🧪 TEST MODE ACTIVATED")
            print(f"   Channel: @{ACCOUNTS_TO_TRACK[0]}")
            print(f"   Videos: 10")
            print(f"   Output: Terminal + Excel file")
            accounts = [ACCOUNTS_TO_TRACK[0]]
            expected_videos = 10
        else:
            print(f"\n✅ Will scrape {len(ACCOUNTS_TO_TRACK)} channel(s):\n")
            for i, account in enumerate(ACCOUNTS_TO_TRACK, 1):
                print(f"   {i}. @{account}")
            accounts = ACCOUNTS_TO_TRACK
            if deep_scrape:
                print("\n🔍 Mode: DEEP SCRAPE (ALL videos, no limit)")
                expected_videos = None
            else:
                print(f"\n📊 Mode: {max_videos} videos per channel")
                expected_videos = max_videos
        
        if not auto_mode:
            input("\n▶️ Press ENTER to start scraping...")
        
        # Load existing data
        existing_data = self.load_existing_excel()
        timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_account_data = {}
        scrape_results = {}
        
        try:
            # Scrape each channel
            for idx, channel_name in enumerate(accounts, 1):
                print("\n" + "="*70)
                if test_mode:
                    print(f"🧪 TEST SCRAPE: @{channel_name}")
                else:
                    print(f"📺 [{idx}/{len(accounts)}] Processing @{channel_name}")
                print("="*70)
                
                try:
                    videos_data, subscribers, total_likes = self.scrape_youtube_channel(
                        channel_name, 
                        max_videos=expected_videos, 
                        deep_scrape=deep_scrape,
                        test_mode=test_mode
                    )
                    
                    scrape_results[channel_name] = {
                        'videos_count': len(videos_data),
                        'subscribers': subscribers,
                        'total_likes': total_likes
                    }
                    
                    if test_mode:
                        print("\n" + "="*70)
                        print("✅ TEST COMPLETE!")
                        print("="*70)
                        print(f"\n📊 Summary:")
                        print(f"   Channel: @{channel_name}")
                        print(f"   Subscribers: {subscribers:,}" if subscribers else "   Subscribers: N/A")
                        print(f"   Videos scraped: {len(videos_data)}")
                        print(f"   Total likes: {total_likes:,}" if total_likes else "   Total likes: N/A")
                        
                        if videos_data:
                            shorts_count = sum(1 for v in videos_data if v.get('is_short', False))
                            print(f"   Shorts: {shorts_count}, Regular videos: {len(videos_data) - shorts_count}")
                            avg_views = sum(v['views'] for v in videos_data) / len(videos_data)
                            avg_engagement = sum(v['engagement'] for v in videos_data) / len(videos_data)
                            print(f"   Average views: {avg_views:,.0f}")
                            print(f"   Average engagement: {avg_engagement:.2f}%")
                    
                    # Create/update DataFrame
                    existing_df = existing_data.get(channel_name, pd.DataFrame())
                    df = self.create_dataframe_for_account(
                        videos_data, subscribers, total_likes, timestamp_col, existing_df
                    )
                    all_account_data[channel_name] = df
                    self.current_data = all_account_data  # For backup
                    
                    if not test_mode:
                        print(f"\n  ✅ @{channel_name} complete!")
                        print(f"  👥 Subscribers: {subscribers:,}" if subscribers else "  👥 Subscribers: N/A")
                        print(f"  🎬 Videos: {len(videos_data)}")
                        print(f"  👍 Total likes: {total_likes:,}" if total_likes else "  👍 Total likes: N/A")
                        
                except Exception as e:
                    print(f"\n  ❌ Error with @{channel_name}: {e}")
                    traceback.print_exc()
                    scrape_results[channel_name] = {
                        'videos_count': 0,
                        'subscribers': None,
                        'total_likes': None
                    }
                    continue
            
            # Save to Excel
            if all_account_data:
                self.save_to_excel(all_account_data)
                self.upload_to_google_drive()
                
                # Handle early terminations
                if self.early_terminations:
                    self.handle_early_terminations(all_account_data, timestamp_col)
                    # Save updated results
                    self.save_to_excel(all_account_data)
                    self.upload_to_google_drive()
            
            # Final summary
            print("\n" + "="*70)
            print("✅ SCRAPING COMPLETE!")
            print("="*70)
            
            total_videos = 0
            for channel, result in scrape_results.items():
                if result['videos_count'] > 0:
                    print(f"\n@{channel}:")
                    print(f"  Videos: {result['videos_count']}")
                    if result['subscribers']:
                        print(f"  Subscribers: {result['subscribers']:,}")
                    if result['total_likes']:
                        print(f"  Total Likes: {result['total_likes']:,}")
                    total_videos += result['videos_count']
            
            print(f"\n📊 Totals:")
            print(f"  Channels scraped: {len(scrape_results)}")
            print(f"  Total videos: {total_videos}")
            print(f"  API quota used: ~{self.api_quota_used} units")
            print(f"  Daily quota remaining: ~{self.api_quota_limit - self.api_quota_used} units")
            
            if self.early_terminations:
                print("\n⚠️  Early terminations:")
                for channel, info in self.early_terminations.items():
                    print(f"  @{channel}: {info['reason']} at {info['videos_scraped']} videos")
            
            print("\n" + "="*70 + "\n")
            
        finally:
            # Ensure backup is saved if interrupted
            if self.interrupted and self.current_data:
                self.save_backup()

    # Methods for master scraper integration
    def scrape_recent_videos(self, channel, limit=30):
        """Scrape recent videos for master scraper (test mode)"""
        videos_data, subscribers, total_likes = self.scrape_youtube_channel(
            channel, max_videos=limit, deep_scrape=False, test_mode=False
        )
        
        # Convert to format expected by master scraper
        videos = []
        for video in videos_data:
            videos.append({
                'id': video['video_id'],
                'title': video['title'],
                'description': '',  # Would need additional API call
                'view_count': video['views'],
                'like_count': video['likes'],
                'comment_count': video['comments'],
                'duration': video['duration'],
                'published_at': video['date']
            })
        
        return videos
    
    def scrape_by_date(self, channel, start_date):
        """Scrape videos from a specific date for master scraper"""
        # Determine if this is deep scrape based on date
        days_back = (datetime.now() - start_date).days
        deep_scrape = days_back > 365  # Deep scrape if more than a year
        
        videos_data, subscribers, total_likes = self.scrape_youtube_channel(
            channel, max_videos=2000, deep_scrape=deep_scrape, test_mode=False
        )
        
        # Filter by date and convert to format expected by master scraper
        videos = []
        for video in videos_data:
            if video.get('date_timestamp'):
                if video['date_timestamp'] >= start_date:
                    videos.append({
                        'id': video['video_id'],
                        'title': video['title'],
                        'description': '',
                        'view_count': video['views'],
                        'like_count': video['likes'],
                        'comment_count': video['comments'],
                        'duration': video['duration'],
                        'published_at': video['date']
                    })
        
        return videos


if __name__ == "__main__":
    scraper = YoutubeScraper()
    scraper.run()
