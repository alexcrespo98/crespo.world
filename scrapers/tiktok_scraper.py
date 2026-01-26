#!/usr/bin/env python3
"""
TikTok Analytics Tracker v2.0
- NEW: Interrupt handler (Ctrl+C saves backup file)
- NEW: Master scraper integration support
- NEW: Early termination detection with recovery option
- NEW: Auto-detection when scraping fails or gets blocked
- Auto-detects accounts from existing Excel file
- Scrapes multiple TikTok accounts
- Configurable scrape days (default: 100, or deep scrape for all available)
- Updates Excel file with separate tabs for each account
- Uses yt-dlp for detailed per-post metrics
- Retries failed screenshot scrapes at the end
"""

import csv
import json
import sys
import subprocess
import re
import os
from datetime import datetime, timedelta
import statistics
import signal
import traceback
from pathlib import Path
import time

# Import after ensuring packages
def ensure_selenium():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        return True
    except ImportError:
        return False

def ensure_pil():
    try:
        from PIL import Image
        import pytesseract
        return True
    except ImportError:
        return False

OUTPUT_EXCEL = "tiktok_analytics_tracker.xlsx"

# Set Tesseract path (cross-platform)
try:
    import pytesseract
    import platform
    if platform.system() == 'Windows':
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    # On Linux/Ubuntu, tesseract should be in PATH or at /usr/bin/tesseract
except:
    pass

class TikTokScraper:
    # Data validation threshold (prevent uploads with insufficient data)
    DATA_VALIDATION_THRESHOLD = 0.9  # New data must have at least 90% of previous count
    
    def __init__(self):
        self.interrupted = False
        self.current_data = {}
        self.early_terminations = {}
        self.failed_accounts = []
        
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
        backup_name = f"tiktok_backup_{timestamp}.xlsx"
        
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
                'failed_accounts': self.failed_accounts
            }
            
            state_file = f"tiktok_state_{timestamp}.json"
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
            'yt_dlp': 'yt-dlp',
            'pandas': 'pandas',
            'openpyxl': 'openpyxl',
            'selenium': 'selenium',
            'PIL': 'Pillow',
            'pytesseract': 'pytesseract'
        }
        
        for module, package in required.items():
            try:
                if module == 'PIL':
                    from PIL import Image
                else:
                    __import__(module)
            except ImportError:
                packages_needed.append(package)
        
        if packages_needed:
            print("📦 Installing required packages...")
            for p in packages_needed:
                self.install_package(p)
            print("✅ All packages installed!")

    def get_accounts_from_excel(self):
        """Auto-detect all account names from existing Excel file"""
        import pandas as pd
        
        if not os.path.exists(OUTPUT_EXCEL):
            print(f"❌ Excel file not found: {OUTPUT_EXCEL}")
            # Return default accounts if no Excel exists
            return [
                "popdartsgame",
                "bucketgolfgame",
                "playbattlegolf",
                "flinggolf",
                "golfponggames",
                "discgogames"
            ]
        
        try:
            xls = pd.ExcelFile(OUTPUT_EXCEL)
            accounts = xls.sheet_names
            
            if not accounts:
                print("❌ No sheets found in Excel file!")
                return None
            
            print(f"✅ Found {len(accounts)} account(s) in Excel file:")
            for i, account in enumerate(accounts, 1):
                print(f"   {i}. @{account}")
            
            return accounts
            
        except Exception as e:
            print(f"❌ Error reading Excel file: {e}")
            return None

    def get_tokcount_stats(self, username):
        """Get followers and likes for a TikTok user from TokCount using screenshots + OCR"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from PIL import Image
        import pytesseract
        
        url = f"https://tokcount.com/?user={username}"
        # Use temp directory for cross-platform compatibility
        screenshot_dir = os.path.join(os.path.expanduser("~"), ".tiktok_scraper_temp")
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        # Add ad blocking
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2
        })
        
        print(f"  🔍 Fetching TokCount stats...")
        
        screenshot_files = []
        driver = None
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            
            # Initial wait for page load
            print(f"  ⏳ Waiting for page to load and numbers to settle...")
            time.sleep(5)
            
            # Try to close any popups/ads
            try:
                # Common close button selectors
                close_buttons = driver.find_elements(By.CSS_SELECTOR, 
                    "button[aria-label='Close'], .close, .modal-close, [class*='close'], [id*='close']")
                for btn in close_buttons:
                    try:
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(0.5)
                    except:
                        pass
            except:
                pass
            
            # Wait for numbers to settle (they change rapidly at first)
            # Check multiple times to see when numbers stabilize
            print(f"  ⏳ Waiting for counter to stabilize...")
            stable_count = 0
            last_text = ""
            
            for attempt in range(6):  # Check up to 6 times
                time.sleep(3)  # Wait 3 seconds between checks
                try:
                    # Get page text
                    current_text = driver.find_element(By.TAG_NAME, "body").text
                    
                    # Extract numbers
                    current_numbers = re.findall(r'\d{1,3}(?:,\d{3})+|\b\d{6,}\b', current_text)
                    
                    # Check if numbers are similar to last check
                    if current_numbers and current_text == last_text:
                        stable_count += 1
                        if stable_count >= 2:  # Numbers stable for 2 checks
                            print(f"  ✅ Counter stabilized")
                            break
                    else:
                        stable_count = 0
                    
                    last_text = current_text
                except:
                    pass
            
            # Additional wait to be safe
            time.sleep(2)
            
            # Take screenshots at different scroll positions
            scroll_positions = [0, 200, 400, 600, 800]
            
            for i, scroll_pos in enumerate(scroll_positions):
                driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(1)
                filename = os.path.join(screenshot_dir, f"tokcount_temp_{username}_{i+1}.png")
                driver.save_screenshot(filename)
                screenshot_files.append(filename)
            
            # Extract text from screenshots 1 and 5
            target_screenshots = [screenshot_files[0], screenshot_files[4]]
            all_text = []
            
            for filename in target_screenshots:
                if os.path.exists(filename):
                    img = Image.open(filename)
                    text = pytesseract.image_to_string(img)
                    all_text.append(text)
            
            combined_text = '\n'.join(all_text)
            
            # Parse for followers and likes
            followers = None
            likes = None
            
            # Find all numbers with commas
            all_numbers = re.findall(r'\d{1,3}(?:,\d{3})+', combined_text)
            all_numbers.extend(re.findall(r'\b\d{6,}\b', combined_text))
            
            # Look for keywords
            lines = combined_text.split('\n')
            for i, line in enumerate(lines):
                if 'follower' in line.lower() and not followers:
                    for j in range(max(0, i-3), min(len(lines), i+3)):
                        line_nums = re.findall(r'\d{1,3}(?:,\d{3})+|\b\d{6,}\b', lines[j])
                        if line_nums:
                            followers = line_nums[0].replace(',', '')
                            break
                
                if 'like' in line.lower() and 'unlike' not in line.lower() and not likes:
                    for j in range(max(0, i-2), min(len(lines), i+3)):
                        line_nums = re.findall(r'\d{1,3}(?:,\d{3})+|\b\d{6,}\b', lines[j])
                        if line_nums:
                            likes = line_nums[0].replace(',', '')
                            break
            
            # Fallback: use largest numbers
            if not followers and not likes and all_numbers:
                unique_nums = list(set(all_numbers))
                sorted_nums = sorted(unique_nums, key=lambda x: int(x.replace(',', '')), reverse=True)
                if not followers and len(sorted_nums) > 0:
                    followers = sorted_nums[0].replace(',', '')
                if not likes and len(sorted_nums) > 1:
                    likes = sorted_nums[1].replace(',', '')
            
            return int(followers) if followers else None, int(likes) if likes else None
            
        except Exception as e:
            print(f"  ⚠️ TokCount error: {e}")
            return None, None
            
        finally:
            if driver:
                driver.quit()
            # Clean up screenshots
            for filename in screenshot_files:
                try:
                    if os.path.exists(filename):
                        os.remove(filename)
                except:
                    pass

    def scrape_tiktok_profile(self, username, max_videos=100):
        """Returns (videos_data, follower_count, total_likes)"""
        import yt_dlp
        
        print(f"  🔍 Scraping {max_videos if max_videos != 9999999 else 'ALL'} posts with yt-dlp...")
        
        ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'skip_download': True,
            'playlistend': max_videos if max_videos != 9999999 else None,
            'writeinfojson': False,
            'ignoreerrors': True,
        }
        
        videos_data = []
        follower_count = None
        total_likes_estimate = None
        early_termination = None
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            profile_url = f"https://www.tiktok.com/@{username}"
            try:
                playlist_info = ydl.extract_info(profile_url, download=False)
            except Exception as e:
                print(f"  ⚠️ First attempt failed, trying with extract_flat...")
                ydl_opts['extract_flat'] = True
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                        playlist_info = ydl2.extract_info(profile_url, download=False)
                except Exception as e2:
                    print(f"  ❌ Could not access profile: {e2}")
                    self.early_terminations[username] = {
                        'reason': 'profile_blocked',
                        'videos_scraped': 0,
                        'message': str(e2)
                    }
                    return [], None, None
            
            if not playlist_info:
                print("  ❌ Could not access profile")
                self.early_terminations[username] = {
                    'reason': 'no_data',
                    'videos_scraped': 0,
                    'message': 'No data returned'
                }
                return [], None, None
            
            follower_count = playlist_info.get('channel_follower_count') or \
                            playlist_info.get('followers') or 0
            total_likes_estimate = playlist_info.get('channel_like_count') or \
                                  playlist_info.get('like_count') or 0
            
            entries = playlist_info.get('entries', [])
            if not entries and 'url' in playlist_info:
                entries = [playlist_info]
            
            posts_to_scrape = entries if max_videos == 9999999 else entries[:max_videos]
            
            # Track consecutive failures
            consecutive_failures = 0
            max_failures = 5
            
            for i, entry in enumerate(posts_to_scrape):
                try:
                    if isinstance(entry, dict) and entry.get('_type') == 'url':
                        with yt_dlp.YoutubeDL({'quiet': True, 'ignoreerrors': True}) as ydl_single:
                            video_info = ydl_single.extract_info(entry['url'], download=False)
                    else:
                        video_info = entry
                    
                    if not video_info:
                        consecutive_failures += 1
                        if consecutive_failures >= max_failures and len(videos_data) > 50:
                            print(f"  ⚠️ Too many failures after {len(videos_data)} videos - likely reached limit")
                            early_termination = {
                                'reason': 'scrape_limit',
                                'videos_scraped': len(videos_data)
                            }
                            break
                        continue
                    
                    consecutive_failures = 0  # Reset on success
                    
                    video_id = video_info.get('id', f"unknown_{i}")
                    views = video_info.get('view_count', 0) or 0
                    likes = video_info.get('like_count', 0) or 0
                    comments = video_info.get('comment_count', 0) or 0
                    shares = video_info.get('repost_count', 0) or 0
                    upload_date = video_info.get('upload_date')
                    
                    if upload_date and len(upload_date) == 8:
                        date_obj = datetime.strptime(upload_date, "%Y%m%d")
                    else:
                        date_obj = datetime.now()
                    
                    engagement = (likes + comments) / views * 100 if views > 0 else 0
                    
                    videos_data.append({
                        'VideoID': video_id,
                        'Date': date_obj.strftime('%Y-%m-%d'),
                        'date_timestamp': date_obj,
                        'Views': views,
                        'Likes': likes,
                        'Comments': comments,
                        'Shares': shares,
                        'EngagementRate': round(engagement, 2)
                    })
                    
                    # Progress update for large scrapes
                    if len(videos_data) % 25 == 0 and max_videos > 100:
                        print(f"    Progress: {len(videos_data)} videos scraped...")
                    
                except Exception as e:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures and len(videos_data) > 50:
                        print(f"  ⚠️ Too many consecutive failures - stopping at {len(videos_data)} videos")
                        early_termination = {
                            'reason': 'consecutive_failures',
                            'videos_scraped': len(videos_data)
                        }
                        break
                    continue
            
            if early_termination:
                self.early_terminations[username] = early_termination
        
        print(f"  ✅ Scraped {len(videos_data)} videos")
        return videos_data, int(follower_count), int(total_likes_estimate)

    def load_existing_excel(self):
        """Load existing Excel file or create empty dict"""
        import pandas as pd
        
        if os.path.exists(OUTPUT_EXCEL):
            try:
                excel_data = pd.read_excel(OUTPUT_EXCEL, sheet_name=None, index_col=0)
                return excel_data
            except Exception as e:
                print(f"⚠️ Could not load existing Excel: {e}")
                return {}
        return {}

    def create_dataframe_for_account(self, videos_data, followers, total_likes, timestamp_col, existing_df=None):
        """Create or update DataFrame for a single account"""
        import pandas as pd
        
        if existing_df is not None and not existing_df.empty:
            df = existing_df.copy()
        else:
            df = pd.DataFrame()
        
        # Add timestamp column if it doesn't exist
        if timestamp_col not in df.columns:
            df[timestamp_col] = None
        
        # Add account-level metrics
        df.loc["followers", timestamp_col] = followers
        df.loc["total_likes", timestamp_col] = total_likes
        df.loc["posts_scraped", timestamp_col] = len(videos_data)
        
        # Add per-post metrics
        for v in videos_data:
            vid = v['VideoID']
            for metric in ['Date', 'Views', 'Likes', 'Comments', 'Shares', 'EngagementRate']:
                row_name = f"post_{vid}_{metric}"
                if row_name not in df.index:
                    df.loc[row_name] = None
                df.loc[row_name, timestamp_col] = v.get(metric, "")
        
        return df

    def save_to_excel(self, all_account_data):
        """Save all account data to multi-tab Excel file, preserving existing data"""
        import pandas as pd
        
        # Read existing data first to merge with new data
        existing_data = self.load_existing_excel()
        
        # Merge existing data with new data
        merged_data = {}
        for username, new_df in all_account_data.items():
            if username in existing_data:
                # Merge: existing data should already be in new_df from create_dataframe_for_account
                # But just to be safe, ensure all columns are preserved
                old_df = existing_data[username]
                # Combine old and new columns
                for col in old_df.columns:
                    if col not in new_df.columns:
                        new_df[col] = old_df[col]
            merged_data[username] = new_df
        
        # Also preserve any accounts that weren't scraped this time
        for username, df in existing_data.items():
            if username not in merged_data:
                merged_data[username] = df
        
        # Write the merged data
        with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl', mode='w') as writer:
            for username, df in merged_data.items():
                sheet_name = username[:31]
                df.to_excel(writer, sheet_name=sheet_name)
        
        print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")
        print(f"   📊 Preserved data for {len(merged_data)} account(s)")

    def validate_data_before_upload(self, new_data):
        """
        Validate that new data contains sufficient information before uploading.
        Prevents overwriting good data with incomplete scrapes.
        
        Returns: (should_upload: bool, reason: str)
        """
        import pandas as pd
        
        # If no existing file, always upload
        if not os.path.exists(OUTPUT_EXCEL):
            return True, "No existing file - safe to upload"
        
        try:
            existing_data = pd.read_excel(OUTPUT_EXCEL, sheet_name=None, index_col=0)
        except Exception as e:
            print(f"  ⚠️  Could not read existing Excel: {e}")
            return True, "Could not read existing file - proceeding with upload"
        
        issues = []
        
        for username, new_df in new_data.items():
            if username not in existing_data:
                continue
            
            old_df = existing_data[username]
            
            if old_df.empty or len(old_df.columns) == 0:
                continue
            
            old_cols = [c for c in old_df.columns]
            if not old_cols:
                continue
            
            # Convert all columns to strings before sorting to avoid datetime/str comparison
            # Then find the actual column object that matches the sorted result
            sorted_str_cols = sorted([str(c) for c in old_cols])
            last_old_col_str = sorted_str_cols[-1]
            # Find the actual column object that matches this string
            last_old_col = next((c for c in old_cols if str(c) == last_old_col_str), old_cols[-1])
            
            if new_df.empty or len(new_df.columns) == 0:
                issues.append(f"@{username}: New data is empty")
                continue
            
            new_cols = list(new_df.columns)
            current_col = new_cols[-1]
            
            # Check posts count
            try:
                old_posts = old_df.loc["posts_scraped", last_old_col] if "posts_scraped" in old_df.index else 0
                new_posts = new_df.loc["posts_scraped", current_col] if "posts_scraped" in new_df.index else 0
                
                old_posts = int(old_posts) if pd.notna(old_posts) else 0
                new_posts = int(new_posts) if pd.notna(new_posts) else 0
                
                # Allow tolerance defined by DATA_VALIDATION_THRESHOLD
                min_acceptable = int(old_posts * self.DATA_VALIDATION_THRESHOLD)
                
                if new_posts < min_acceptable:
                    issues.append(f"@{username}: New scrape has {new_posts} posts vs {old_posts} previously")
            except Exception as e:
                print(f"  ⚠️  Could not compare posts for @{username}: {e}")
        
        if issues:
            print("\n" + "="*70)
            print("⚠️  DATA VALIDATION WARNING")
            print("="*70)
            print("\nNew data appears to have less content than previous scrape:")
            for issue in issues:
                print(f"  • {issue}")
            print("\n❌ Upload BLOCKED to prevent data loss.")
            return False, "Insufficient data - upload blocked"
        
        return True, "Data validation passed"

    def validate_scraped_data(self, username, followers, total_likes, existing_df):
        """
        Validate scraped data for logical consistency.
        Checks:
        1. New values should be reasonably close to previous non-zero values
        2. Detect if followers and likes values appear to be swapped
        
        Returns: (is_valid: bool, reason: str)
        """
        import pandas as pd
        
        # Check if we have previous data for comparison
        if not existing_df.empty and len(existing_df.columns) > 0:
            # Get sorted columns
            col_str_map = {str(c): c for c in existing_df.columns}
            sorted_str_cols = sorted(col_str_map.keys())
            cols = [col_str_map[str_col] for str_col in sorted_str_cols]
            
            # Find last non-zero followers and total_likes
            last_followers = None
            last_likes = None
            
            for col in reversed(cols):
                if 'followers' in existing_df.index:
                    val = existing_df.loc['followers', col]
                    if pd.notna(val) and val > 0 and last_followers is None:
                        last_followers = val
                
                if 'total_likes' in existing_df.index:
                    val = existing_df.loc['total_likes', col]
                    if pd.notna(val) and val > 0 and last_likes is None:
                        last_likes = val
                
                if last_followers is not None and last_likes is not None:
                    break
            
            # Check if values are swapped (followers and likes switched)
            if last_followers and last_likes and followers and total_likes:
                # If current followers are close to old likes AND current likes close to old followers
                # This indicates a swap
                follower_like_ratio = abs(followers - last_likes) / max(last_likes, 1)
                like_follower_ratio = abs(total_likes - last_followers) / max(last_followers, 1)
                
                if follower_like_ratio < 0.1 and like_follower_ratio < 0.1:
                    return False, f"Possible swap detected: followers={followers:,} (prev likes={last_likes:,}), likes={total_likes:,} (prev followers={last_followers:,})"
            
            # Check if values are reasonably close to previous (allow 3x growth or 50% decline)
            if last_followers and followers:
                ratio = followers / last_followers
                if ratio > 3.0 or ratio < 0.5:
                    return False, f"Followers changed drastically: {last_followers:,} -> {followers:,} (ratio: {ratio:.2f}x)"
            
            if last_likes and total_likes:
                ratio = total_likes / last_likes
                if ratio > 3.0 or ratio < 0.5:
                    return False, f"Total likes changed drastically: {last_likes:,} -> {total_likes:,} (ratio: {ratio:.2f}x)"
        
        return True, "Data looks valid"

    def interpolate_zero_values(self, all_account_data):
        """
        Interpolate zero values in the data to fill gaps from failed scrapes.
        Uses average of surrounding values (left and right) for better visual representation.
        
        Args:
            all_account_data: Dict of {username: DataFrame}
            
        Returns:
            all_account_data: Same dict with interpolated values
        """
        import pandas as pd
        import numpy as np
        
        for username, df in all_account_data.items():
            if df.empty or len(df.columns) == 0:
                continue
            
            # Convert all columns to strings before sorting to avoid datetime/str comparison
            # Then find the actual column objects that match the sorted result
            col_str_map = {str(c): c for c in df.columns}
            sorted_str_cols = sorted(col_str_map.keys())
            cols = [col_str_map[str_col] for str_col in sorted_str_cols]
            
            # Track interpolations for logging
            interpolation_count = {}
            
            # Interpolate account-level metrics
            for metric in ['followers', 'total_likes', 'posts_scraped']:
                if metric not in df.index:
                    continue
                
                row_data = df.loc[metric, cols].copy()
                original_zeros = (row_data == 0).sum()
                
                if original_zeros > 0:
                    # Interpolate using average of left and right non-zero values
                    for i, col in enumerate(cols):
                        if row_data[col] == 0:
                            left_val = None
                            right_val = None
                            
                            # Find left non-zero value
                            for j in range(i - 1, -1, -1):
                                if row_data[cols[j]] != 0:
                                    left_val = row_data[cols[j]]
                                    break
                            
                            # Find right non-zero value
                            for j in range(i + 1, len(cols)):
                                if row_data[cols[j]] != 0:
                                    right_val = row_data[cols[j]]
                                    break
                            
                            # Interpolate based on available values
                            if left_val is not None and right_val is not None:
                                # Use average of both
                                row_data[col] = (left_val + right_val) / 2
                            elif left_val is not None:
                                # Only left available, use it
                                row_data[col] = left_val
                            elif right_val is not None:
                                # Only right available, use it
                                row_data[col] = right_val
                    
                    # Update the dataframe
                    df.loc[metric, cols] = row_data
                    
                    # Count actual interpolations (zeros that were filled)
                    filled_count = original_zeros - (df.loc[metric, cols] == 0).sum()
                    if filled_count > 0:
                        interpolation_count[metric] = filled_count
            
            # Log interpolations
            if interpolation_count:
                for metric, count in interpolation_count.items():
                    print(f"✅ @{username}: Interpolated {count} zero value(s) for {metric}")
        
        return all_account_data

    def upload_to_google_drive(self, all_account_data=None):
        """
        Upload to Google Drive with data validation.
        
        Args:
            all_account_data: Optional dict of account data for validation.
        """
        print("\n" + "="*70)
        print("☁️  Uploading to Google Drive...")
        print("="*70)
        
        # Validate data if provided
        if all_account_data:
            should_upload, reason = self.validate_data_before_upload(all_account_data)
            print(f"  📊 Validation: {reason}")
            if not should_upload:
                return False
            
            # Interpolate zero values before upload
            all_account_data = self.interpolate_zero_values(all_account_data)
        
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

    def show_account_summary(self, username, df):
        """Show summary for a single account"""
        if df.empty or df.shape[1] < 1:
            print(f"  📊 No data yet for @{username}")
            return
        
        last_col = df.columns[-1]
        
        try:
            followers = df.loc["followers", last_col]
            total_likes = df.loc["total_likes", last_col]
            posts_count = df.loc["posts_scraped", last_col]
            
            print(f"\n  👤 @{username}")
            print(f"  👥 Followers: {int(followers):,}" if followers else "  👥 Followers: N/A")
            print(f"  ❤️  Total Likes: {int(total_likes):,}" if total_likes else "  ❤️  Total Likes: N/A")
            print(f"  🎬 Posts Tracked: {int(posts_count)}" if posts_count else "  🎬 Posts: N/A")
            
            # Show change if there's previous data
            if df.shape[1] >= 2:
                prev_col = df.columns[-2]
                prev_followers = df.loc["followers", prev_col]
                if prev_followers and followers:
                    diff = int(followers) - int(prev_followers)
                    if diff != 0:
                        change = f"+{diff:,}" if diff > 0 else f"{diff:,}"
                        print(f"  📈 Change: {change} followers")
        except Exception as e:
            print(f"  ⚠️ Could not display summary: {e}")

    def display_test_results(self, videos_data, followers, total_likes):
        """Display test mode results in terminal only"""
        print("\n" + "="*70)
        print("🧪 TEST MODE RESULTS")
        print("="*70)
        
        print(f"\n📊 Account Summary:")
        print(f"   👤 Account: @popdartsgame")
        print(f"   👥 Followers: {followers:,}" if followers else "   👥 Followers: N/A")
        print(f"   ❤️  Total Likes: {total_likes:,}" if total_likes else "   ❤️  Total Likes: N/A")
        print(f"   🎬 Videos scraped: {len(videos_data)}")
        
        if videos_data:
            print(f"\n📹 Individual Post Metrics:")
            print("-" * 70)
            
            for i, video in enumerate(videos_data, 1):
                print(f"\nPost #{i}:")
                print(f"  📅 Date: {video['Date']}")
                print(f"  👁️  Views: {video['Views']:,}")
                print(f"  ❤️  Likes: {video['Likes']:,}")
                print(f"  💬 Comments: {video['Comments']:,}")
                print(f"  🔄 Shares: {video['Shares']:,}")
                print(f"  📈 Engagement Rate: {video['EngagementRate']}%")
                print(f"  🔗 Video ID: {video['VideoID']}")
            
            # Calculate and show averages
            avg_views = sum(v['Views'] for v in videos_data) / len(videos_data)
            avg_likes = sum(v['Likes'] for v in videos_data) / len(videos_data)
            avg_engagement = sum(v['EngagementRate'] for v in videos_data) / len(videos_data)
            
            print("\n" + "="*70)
            print("📊 AVERAGE METRICS:")
            print(f"   Avg Views: {avg_views:,.0f}")
            print(f"   Avg Likes: {avg_likes:,.0f}")
            print(f"   Avg Engagement: {avg_engagement:.2f}%")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETE - No files were updated")
        print("="*70)

    def get_scrape_config(self):
        """Ask user for scrape configuration at the start"""
        print("\n" + "="*70)
        print("⚙️  SCRAPE CONFIGURATION")
        print("="*70)
        
        while True:
            print("\nSelect scraping option:")
            print("  1. Custom number of posts (default: 100)")
            print("  2. Deep scrape (back 2 years or to beginning of account)")
            print("  3. Test mode (15 reels on @popdartsgame, displays all 15)")
            
            user_input = input("\nEnter your choice (1, 2, or 3): ").strip()
            
            if user_input == "1" or user_input == "":
                # Ask for custom number
                num_input = input("📊 How many posts per account? [100]: ").strip()
                if num_input == "":
                    print("\n✅ Will scrape 100 posts per account")
                    return 100, False
                else:
                    try:
                        num_posts = int(num_input)
                        if num_posts > 0:
                            print(f"\n✅ Will scrape {num_posts} posts per account")
                            return num_posts, False
                        else:
                            print("❌ Please enter a positive number")
                    except ValueError:
                        print("❌ Invalid input. Please enter a number")
            
            elif user_input == "2":
                print("\n🔥 Deep scrape selected - will scrape ALL available posts!")
                return 9999999, False
            
            elif user_input == "3":
                print("\n🧪 Test mode selected - will scrape 15 posts from @popdartsgame")
                return 15, True
            
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3")

    def retry_failed_scrapes(self, failed_accounts, auto_retry=False):
        """Retry screenshot scraping for accounts that returned N/A"""
        if not failed_accounts:
            return {}
        
        print("\n" + "="*70)
        print("🔄 RETRY FAILED SCREENSHOT SCRAPES")
        print("="*70)
        print(f"\nThe following accounts had N/A for follower count:")
        for username in failed_accounts:
            print(f"  • @{username}")
        
        # Auto-retry if enabled, otherwise prompt
        if auto_retry:
            print("\n🔄 Auto-retry enabled, retrying screenshot scraping...")
            retry = True
        else:
            while True:
                retry_input = input("\n🔄 Would you like to retry screenshot scraping? (y/n): ").strip().lower()
                if retry_input in ["y", "yes"]:
                    retry = True
                    break
                elif retry_input in ["n", "no"]:
                    return {}
                else:
                    print("❌ Please type 'y' or 'n'.")
        
        if not retry:
            return {}
        
        print("\n📸 Retrying screenshot scrapes...")
        retry_results = {}
        
        for username in failed_accounts:
            print(f"\n  🔄 Retrying @{username}...")
            tokcount_followers, tokcount_likes = self.get_tokcount_stats(username)
            if tokcount_followers:
                retry_results[username] = (tokcount_followers, tokcount_likes)
                print(f"  ✅ Successfully retrieved: {tokcount_followers:,} followers")
            else:
                print(f"  ❌ Still N/A")
        
        return retry_results

    def handle_early_terminations(self, all_account_data, timestamp_col):
        """Handle accounts that were cut off early"""
        if not self.early_terminations:
            return
        
        print("\n" + "="*70)
        print("⚠️  EARLY TERMINATION DETECTED")
        print("="*70)
        
        for username, termination_info in self.early_terminations.items():
            print(f"\n@{username}:")
            print(f"  Reason: {termination_info['reason'].replace('_', ' ').title()}")
            print(f"  Videos scraped: {termination_info.get('videos_scraped', 0)}")
            if 'message' in termination_info:
                print(f"  Message: {termination_info['message'][:100]}")
        
        retry = input("\n🔄 Would you like to retry these accounts? (y/n): ").strip().lower()
        
        if retry == 'y':
            print("\n🔄 Attempting to retry accounts...")
            for username in self.early_terminations.keys():
                print(f"\n📱 Re-attempting @{username}...")
                try:
                    # Try with a smaller batch
                    videos_data, followers, total_likes = self.scrape_tiktok_profile(
                        username, max_videos=50
                    )
                    
                    if len(videos_data) > 0:
                        print(f"  ✅ Got {len(videos_data)} videos on retry!")
                        existing_df = all_account_data.get(username)
                        df = self.create_dataframe_for_account(
                            videos_data, followers, total_likes, timestamp_col, existing_df
                        )
                        all_account_data[username] = df
                    else:
                        print(f"  ℹ️  Still unable to scrape")
                except Exception as e:
                    print(f"  ❌ Retry failed: {e}")

    def run(self, max_posts=None, auto_mode=False, auto_retry=False):
        """Main execution function"""
        import pandas as pd
        
        self.ensure_packages()
        
        print("\n" + "="*70)
        print("🎯 TikTok Analytics Tracker v2.0")
        print("="*70)
        
        # Get scrape configuration if not provided
        test_mode = False
        if max_posts is None and not auto_mode:
            max_posts, test_mode = self.get_scrape_config()
        elif max_posts is None:
            max_posts = 100  # Default for auto mode
        
        if test_mode:
            # TEST MODE - Only scrape @popdartsgame and display in terminal
            print("\n" + "="*70)
            print("🧪 TEST MODE ACTIVATED")
            print("="*70)
            print(f"   Account: @popdartsgame")
            print(f"   Posts to scrape: 15")
            
            try:
                # Get TokCount stats
                print("\nFetching account stats...")
                tokcount_followers, tokcount_likes = self.get_tokcount_stats("popdartsgame")
                
                # Get detailed post metrics
                print("\nScraping posts...")
                videos_data, ytdlp_followers, ytdlp_likes = self.scrape_tiktok_profile(
                    "popdartsgame", max_videos=15  # Parameter name is max_videos per method signature
                )
                
                # Use best available data
                followers = tokcount_followers if tokcount_followers else ytdlp_followers
                total_likes = tokcount_likes if tokcount_likes else ytdlp_likes
                
                # Display results in terminal only
                self.display_test_results(videos_data, followers, total_likes)
                
            except Exception as e:
                print(f"\n❌ Test mode error: {e}")
                traceback.print_exc()
            
            return  # Exit after test mode
        
        # NORMAL MODE - Auto-detect accounts and update Excel
        accounts_to_scrape = self.get_accounts_from_excel()
        
        if not accounts_to_scrape:
            print("\n❌ Could not detect accounts. Make sure the Excel file exists!")
            return
        
        scrape_type = "ALL posts" if max_posts == 9999999 else f"{max_posts} posts"
        print(f"\n📊 Scraping {scrape_type} per account")
        print(f"✅ Will update {len(accounts_to_scrape)} account(s)")
        
        # Load existing data
        existing_data = self.load_existing_excel()
        timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_account_data = {}
        failed_screenshot_accounts = []
        
        try:
            # Scrape each account
            for idx, username in enumerate(accounts_to_scrape, 1):
                print("\n" + "="*70)
                print(f"📱 [{idx}/{len(accounts_to_scrape)}] Processing @{username}")
                print("="*70)
                
                try:
                    # Get existing data for validation
                    existing_df = existing_data.get(username, pd.DataFrame())
                    
                    # Try up to 3 times with validation
                    max_attempts = 3
                    success = False
                    
                    for attempt in range(1, max_attempts + 1):
                        if attempt > 1:
                            print(f"\n  🔄 Retry attempt {attempt}/{max_attempts} (waiting 10 seconds...)")
                            time.sleep(10)  # Wait longer between retries
                        
                        # Get TokCount stats
                        tokcount_followers, tokcount_likes = self.get_tokcount_stats(username)
                        
                        # Track failed screenshot scrapes
                        if tokcount_followers is None and attempt == 1:
                            failed_screenshot_accounts.append(username)
                        
                        # Get detailed post metrics
                        videos_data, ytdlp_followers, ytdlp_likes = self.scrape_tiktok_profile(
                            username, max_posts
                        )
                        
                        # Use best available data
                        followers = tokcount_followers if tokcount_followers else ytdlp_followers
                        total_likes = tokcount_likes if tokcount_likes else ytdlp_likes
                        
                        # Validate the scraped data
                        is_valid, reason = self.validate_scraped_data(username, followers, total_likes, existing_df)
                        
                        if is_valid:
                            # Create/update DataFrame
                            df = self.create_dataframe_for_account(
                                videos_data, followers, total_likes, timestamp_col, existing_df
                            )
                            all_account_data[username] = df
                            self.current_data = all_account_data  # For backup
                            
                            # Show summary
                            self.show_account_summary(username, df)
                            success = True
                            break
                        else:
                            print(f"  ⚠️  Validation failed: {reason}")
                            if attempt < max_attempts:
                                print(f"  🔄 Will retry with longer wait time...")
                            else:
                                print(f"  ❌ Max retries reached. Using data anyway but flagging issue.")
                                # Use the data anyway but log the issue
                                df = self.create_dataframe_for_account(
                                    videos_data, followers, total_likes, timestamp_col, existing_df
                                )
                                all_account_data[username] = df
                                self.current_data = all_account_data
                                self.show_account_summary(username, df)
                    
                except Exception as e:
                    print(f"\n  ❌ Error with @{username}: {e}")
                    traceback.print_exc()
                    self.failed_accounts.append(username)
                    continue
            
            # Retry failed screenshot scrapes
            retry_results = self.retry_failed_scrapes(failed_screenshot_accounts, auto_retry=auto_retry)
            
            # Update data with retry results
            if retry_results:
                for username, (followers, total_likes) in retry_results.items():
                    if username in all_account_data:
                        df = all_account_data[username]
                        df.loc["followers", timestamp_col] = followers
                        df.loc["total_likes", timestamp_col] = total_likes
                        all_account_data[username] = df
            
            # Save to Excel
            print("\n" + "="*70)
            self.save_to_excel(all_account_data)
            self.upload_to_google_drive(all_account_data)
            
            # Handle early terminations
            if self.early_terminations:
                self.handle_early_terminations(all_account_data, timestamp_col)
                # Save updated results
                self.save_to_excel(all_account_data)
                self.upload_to_google_drive(all_account_data)
            
            print("\n✅ All accounts scraped successfully!")
            print(f"📁 Updated: '{OUTPUT_EXCEL}'")
            
            if self.early_terminations:
                print("\n⚠️  Early terminations:")
                for username, info in self.early_terminations.items():
                    print(f"  @{username}: {info['reason']} at {info.get('videos_scraped', 0)} videos")
            
            if self.failed_accounts:
                print("\n❌ Failed accounts:")
                for username in self.failed_accounts:
                    print(f"  @{username}")
            
            print("="*70 + "\n")
            
        finally:
            # Ensure backup is saved if interrupted
            if self.interrupted and self.current_data:
                self.save_backup()

    # Methods for master scraper integration
    def scrape_recent_videos(self, account, limit=30):
        """Scrape recent videos for master scraper (test mode)"""
        videos_data, followers, total_likes = self.scrape_tiktok_profile(
            account, max_videos=limit
        )
        
        # Convert to format expected by master scraper
        videos = []
        for video in videos_data:
            videos.append({
                'id': video['VideoID'],
                'url': f"https://www.tiktok.com/@{account}/video/{video['VideoID']}",
                'description': '',  # Would need additional scraping
                'play_count': video['Views'],
                'digg_count': video['Likes'],
                'comment_count': video['Comments'],
                'share_count': video['Shares'],
                'create_time': video['Date']
            })
        
        return videos
    
    def scrape_by_date(self, account, start_date):
        """Scrape videos from a specific date for master scraper"""
        # TikTok doesn't easily allow date-based filtering, so we scrape all and filter
        videos_data, followers, total_likes = self.scrape_tiktok_profile(
            account, max_videos=9999999  # Get all available
        )
        
        # Filter by date and convert to format expected by master scraper
        videos = []
        for video in videos_data:
            if video.get('date_timestamp'):
                if video['date_timestamp'] >= start_date:
                    videos.append({
                        'id': video['VideoID'],
                        'url': f"https://www.tiktok.com/@{account}/video/{video['VideoID']}",
                        'description': '',
                        'play_count': video['Views'],
                        'digg_count': video['Likes'],
                        'comment_count': video['Comments'],
                        'share_count': video['Shares'],
                        'create_time': video['Date']
                    })
        
        return videos


if __name__ == "__main__":
    scraper = TikTokScraper()
    scraper.run()
