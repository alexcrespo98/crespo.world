#!/usr/bin/env python3
"""
Instagram Reels Analytics Tracker v3.0
- NEW: Auto-detection when running out of posts (no more infinite waiting)
- NEW: Interrupt handler (Ctrl+C saves backup file)
- NEW: Master scraper integration support
- NEW: Early termination detection with recovery option
- Arrow scrape FIRST to establish true order
- Hover scrape validates starting position and scrolls up if needed
- Includes pinned posts in final data (marked as pinned)
- Smart cross-reference between hover (reels) and arrow (main) data
- Hybrid method: arrow key navigation + hover scrape
- Updates Excel with separate tabs per account
- Auto-uploads to Google Drive
- MODIFIED: Deep scrape now goes back 2 years or to beginning of account
- IMPROVED: Better debugging for hover scrape comment extraction
"""

import sys
import subprocess
import os
from datetime import datetime, timedelta
import time
import re
import requests
import json
import logging
import signal
import traceback
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

OUTPUT_EXCEL = "instagram_reels_analytics_tracker.xlsx"

# Accounts to track
ACCOUNTS_TO_TRACK = [
    "popdartsgame",
    "bucketgolfgame",
    "playbattlegolf",
    "flinggolf",
    "golfpong.games",
    "discgogames",
    "low_tide_golf"
]

INSTAGRAM_COOKIES = [
    {'name': 'sessionid',  'value': '8438482535%3AH01dy1dQG6nQnk%3A17%3AAYiGfiuNFMl1AOwws5VAC0ljZQuYn4BgQEzQdwhKeg', 'domain': '.instagram.com'},
    {'name': 'csrftoken',  'value': 'j9vt2Y4yXJ2j1OfxN1fe1Fj47ZEHUZgX', 'domain': '.instagram.com'},
    {'name': 'ds_user_id', 'value': '8438482535', 'domain': '.instagram.com'},
    {'name': 'mid',        'value': 'aRqN7gALAAFE_ZLG2YR4s_jAJbWN', 'domain': '.instagram.com'},
    {'name': 'ig_did',     'value': 'C4BB1B54-EE7F-44CE-839C-A6522013D97A', 'domain': '.instagram.com'},
    {'name': 'datr',       'value': '7Y0aabbcI4vK3rldO6uL60Mr', 'domain': '.instagram.com'},
    {'name': 'rur',        'value': '"RVA\0548438482535\0541795498046:01fea08331d20cd7101847a41e2bda4ddefaac288d49493694a6b359884fa576c75219f0"', 'domain': '.instagram.com'},
    {'name': 'ig_nrcb',    'value': '1', 'domain': '.instagram.com'},
    {'name': 'wd',         'value': '879x639', 'domain': '.instagram.com'},
    {'name': 'dpr',        'value': '1.5', 'domain': '.instagram.com'},
]

class InstagramScraper:
    def __init__(self):
        self.driver = None
        self.interrupted = False
        self.current_data = {}
        self.early_terminations = {}
        
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
        
        # Clean up driver
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        print("\n✅ Backup saved. You can resume from where you left off.")
        sys.exit(0)
    
    def save_backup(self):
        """Save backup file with current progress"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"instagram_backup_{timestamp}.xlsx"
        
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
                'early_terminations': self.early_terminations
            }
            
            state_file = f"instagram_state_{timestamp}.json"
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
            'selenium': 'selenium',
            'webdriver_manager': 'webdriver-manager',
            'pandas': 'pandas',
            'openpyxl': 'openpyxl',
            'requests': 'requests'
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

    def select_browser(self):
        print("\n" + "="*70)
        print("🌐 SELECT BROWSER")
        print("="*70)
        print("\n1. Chrome (Recommended)")
        print("2. Firefox")
        print()
        while True:
            choice = input("Enter your choice (1 or 2, default=Chrome): ").strip()
            if choice == '1' or choice == '':
                return 'chrome'
            elif choice == '2':
                return 'firefox'
            else:
                print("Invalid choice. Please enter 1 or 2.")

    def get_exact_follower_count(self, username):
        username = username.replace('@', '')
        url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        headers = {
            'User-Agent': 'Instagram 76.0.0.15.395 Android (24/7.0; 640dpi; 1440x2560; samsung; SM-G930F; herolte; samsungexynos8890; en_US; 138226743)',
            'x-ig-app-id': '936619743392459',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            user_data = data['data']['user']
            follower_count = user_data['edge_followed_by']['count']
            return follower_count
        except:
            return None

    def parse_number(self, text):
        if not text:
            return None
        text = str(text).strip().upper().replace(',', '')
        match = re.match(r'([\d.]+)([KMB]?)', text)
        if match:
            number, suffix = match.groups()
            number = float(number)
            multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
            if suffix in multipliers:
                number *= multipliers[suffix]
            return int(number)
        return None

    def parse_date_to_timestamp(self, date_str):
        if not date_str:
            return None
        try:
            if 'T' in date_str:
                date_str = date_str.replace('Z', '').split('.')[0]
                return datetime.fromisoformat(date_str)
        except:
            pass
        return None

    def is_video_post(self, element):
        try:
            video_indicators = element.find_elements(By.XPATH, ".//*[name()='svg'][@aria-label='Clip'] | .//*[name()='svg'][@aria-label='Video']")
            if video_indicators:
                return True
            href = element.get_attribute('href')
            if href and '/reel/' in href:
                return True
            carousel_indicators = element.find_elements(By.XPATH, ".//*[name()='svg'][@aria-label='Carousel']")
            if carousel_indicators:
                return True
            return False
        except:
            return True

    def setup_driver(self, browser='chrome'):
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.firefox import GeckoDriverManager
        
        if browser == 'chrome':
            print("  🌐 Setting up Chrome driver...")
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--disable-logging")
            service = ChromeService(ChromeDriverManager().install())
            service.log_path = os.devnull
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            print("  🦊 Setting up Firefox driver...")
            firefox_options = FirefoxOptions()
            firefox_options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0")
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=firefox_options)
            driver.maximize_window()
        
        print("  🌐 Loading Instagram...")
        driver.get("https://www.instagram.com")
        time.sleep(3)
        print("  🍪 Loading cookies...")
        for cookie in INSTAGRAM_COOKIES:
            driver.add_cookie(cookie)
        driver.refresh()
        time.sleep(3)
        return driver

    def extract_reel_data_from_overlay(self, driver):
        data = {
            'reel_id': None,
            'date': None,
            'date_display': None,
            'date_timestamp': None,
            'likes': None,
            'comments': None,
        }
        try:
            current_url = driver.current_url
            if '/reel/' in current_url:
                data['reel_id'] = current_url.split('/reel/')[-1].rstrip('/').split('?')[0]
            elif '/p/' in current_url:
                data['reel_id'] = current_url.split('/p/')[-1].rstrip('/').split('?')[0]
            
            try:
                time_elements = driver.find_elements(By.TAG_NAME, "time")
                if time_elements:
                    time_elem = time_elements[0]
                    data['date'] = time_elem.get_attribute('datetime')
                    data['date_display'] = time_elem.text
                    data['date_timestamp'] = self.parse_date_to_timestamp(data['date'])
            except:
                pass
            
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                others_match = re.search(r'and\s+([\d,.]+[KMB]?)\s+others', body_text, re.IGNORECASE)
                if others_match:
                    data['likes'] = self.parse_number(others_match.group(1))
                else:
                    like_match = re.search(r'([\d,.]+[KMB]?)\s+likes?', body_text, re.IGNORECASE)
                    if like_match:
                        data['likes'] = self.parse_number(like_match.group(1))
            except:
                pass
            
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                comment_patterns = [
                    r'View all ([\d,.]+[KMB]?)\s+comments?',
                    r'([\d,.]+[KMB]?)\s+comments?'
                ]
                for pattern in comment_patterns:
                    comment_match = re.search(pattern, body_text, re.IGNORECASE)
                    if comment_match:
                        data['comments'] = self.parse_number(comment_match.group(1))
                        break
            except:
                pass
        except:
            pass
        return data

    def detect_pinned_posts(self, initial_reels):
        dated_reels = [(i, r) for i, r in enumerate(initial_reels) if r.get('date_timestamp')]
        if len(dated_reels) < 2:
            return 0
        
        newest_idx = 0
        newest_date = dated_reels[0][1]['date_timestamp']
        for i, (idx, reel) in enumerate(dated_reels):
            if reel['date_timestamp'] > newest_date:
                newest_date = reel['date_timestamp']
                newest_idx = idx
        return newest_idx

    def arrow_scrape_reels(self, driver, username, max_reels=100, deep_scrape=False, test_mode=False, use_main_profile=False):
        if use_main_profile:
            profile_url = f"https://www.instagram.com/{username}/"
            print(f"  🔄 Arrow scrape using MAIN PROFILE fallback...")
        else:
            profile_url = f"https://www.instagram.com/{username}/reels/"
        
        driver.get(profile_url)
        time.sleep(5)
        
        if use_main_profile:
            post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/') or contains(@href, '/reel/')]")
            first_video_link = None
            for link in post_links:
                if self.is_video_post(link):
                    first_video_link = link
                    break
            if not first_video_link:
                print(f"  ⚠️  No videos found on main profile")
                return [], 0, False, None
            reel_links = [first_video_link]
        else:
            reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
        
        if not reel_links:
            return [], 0, False, None
        
        driver.execute_script("arguments[0].click();", reel_links[0])
        time.sleep(3)
        
        if test_mode:
            print(f"\n  🧪 STEP 1: Arrow scrape from {'MAIN PROFILE' if use_main_profile else '/reels/'} (establishing order)...")
        else:
            print(f"  📅 Step 1: Arrow key scraping (establishing order)...")
        
        consecutive_failures = 0
        FAILURE_THRESHOLD = 3
        initial_reels = []
        
        # Initial scrape to detect pinned posts
        for idx in range(min(5, max_reels)):
            try:
                time.sleep(1)
                data = self.extract_reel_data_from_overlay(driver)
                if not data.get('reel_id'):
                    consecutive_failures += 1
                    if consecutive_failures >= FAILURE_THRESHOLD and not use_main_profile:
                        print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive failures detected - triggering fallback!")
                        return [], 0, True, None
                    break
                
                if data.get('likes') is None and data.get('date') is None:
                    consecutive_failures += 1
                    if consecutive_failures >= FAILURE_THRESHOLD and not use_main_profile:
                        print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive N/A detected - triggering fallback!")
                        return [], 0, True, None
                else:
                    consecutive_failures = 0
                
                initial_reels.append(data)
                if idx < 4:
                    body = driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.ARROW_RIGHT)
                    time.sleep(1.5)
            except:
                break
        
        if len(initial_reels) == 0:
            print(f"  ⚠️  Arrow scrape failed - no data retrieved")
            return [], 0, False, None
        
        pinned_count = self.detect_pinned_posts(initial_reels)
        if test_mode and pinned_count > 0:
            print(f"    📌 Detected {pinned_count} pinned post(s) - will include in final data")
        
        # Go back to start
        for _ in range(len(initial_reels) - 1):
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ARROW_LEFT)
            time.sleep(0.8)
        
        arrow_data = []
        cutoff_date = datetime.now() - timedelta(days=730)  # 2 years
        max_iterations = 2000 if deep_scrape else max_reels
        consecutive_failures = 0
        consecutive_old_posts = 0
        early_termination = None
        
        for idx in range(max_iterations):
            try:
                time.sleep(1)
                data = self.extract_reel_data_from_overlay(driver)
                
                # Check if we've run out of posts
                if not data.get('reel_id'):
                    consecutive_failures += 1
                    if consecutive_failures >= FAILURE_THRESHOLD:
                        if len(arrow_data) > 100:
                            print(f"  ⚠️  Reached end of posts after {len(arrow_data)} reels")
                            early_termination = {
                                'reason': 'end_of_posts',
                                'reels_scraped': len(arrow_data),
                                'last_date': arrow_data[-1].get('date_timestamp') if arrow_data else None
                            }
                            break
                        elif not use_main_profile:
                            print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive failures - triggering fallback!")
                            return arrow_data, pinned_count, True, None
                    if test_mode:
                        print(f"    ⚠️  Arrow scrape stopped at {idx} - no more data")
                    break
                
                if data.get('likes') is None and data.get('date') is None:
                    consecutive_failures += 1
                    if consecutive_failures >= FAILURE_THRESHOLD:
                        if len(arrow_data) > 100:
                            print(f"  ⚠️  Data quality degraded after {len(arrow_data)} reels - likely end of posts")
                            early_termination = {
                                'reason': 'data_quality',
                                'reels_scraped': len(arrow_data),
                                'last_date': arrow_data[-1].get('date_timestamp') if arrow_data else None
                            }
                            break
                        elif not use_main_profile:
                            print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive N/A - triggering fallback!")
                            return arrow_data, pinned_count, True, None
                else:
                    consecutive_failures = 0
                
                # Check if we've gone back far enough for deep scrape
                if deep_scrape and data.get('date_timestamp'):
                    if data['date_timestamp'] < cutoff_date:
                        consecutive_old_posts += 1
                        if consecutive_old_posts >= 5:
                            print(f"    📅 Reached 2-year cutoff date ({cutoff_date.strftime('%Y-%m-%d')})")
                            print(f"    ✅ Deep scrape complete: {len(arrow_data)} reels collected")
                            break
                    else:
                        consecutive_old_posts = 0
                
                data['is_pinned'] = (idx < pinned_count)
                arrow_data.append(data)
                
                if test_mode and idx < max_reels:
                    reel_id = data.get('reel_id', 'N/A')
                    date = data.get('date_display', 'N/A')
                    likes = data.get('likes')
                    comments = data.get('comments')
                    
                    # Format likes and comments to distinguish N/A from 0
                    likes_str = 'N/A' if likes is None else str(likes)
                    comments_str = 'N/A' if comments is None else str(comments)
                    
                    pinned_marker = " 📌PINNED" if data['is_pinned'] else ""
                    print(f"    [{idx+1}] {reel_id}: {date}, likes={likes_str}, comments={comments_str}{pinned_marker}")
                elif not test_mode and deep_scrape and idx % 25 == 0:
                    if data.get('date_timestamp'):
                        days_ago = (datetime.now() - data['date_timestamp']).days
                        print(f"    Arrow progress: {idx + 1} reels... (current: ~{days_ago} days ago)")
                    else:
                        print(f"    Arrow progress: {idx + 1} reels...")
                
                if idx < max_iterations - 1:
                    body = driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.ARROW_RIGHT)
                    time.sleep(1.5)
            except:
                if test_mode:
                    print(f"    ✅ Arrow scrape complete: {idx + 1} reels (including {pinned_count} pinned)")
                break
        
        if test_mode:
            print(f"\n  📊 Arrow scrape complete: {len(arrow_data)} reels (including {pinned_count} pinned)")
        
        return arrow_data, pinned_count, False, early_termination

    def extract_views_from_container(self, container):
        try:
            text = container.text
            numbers = re.findall(r'\b([\d,.]+[KMB]?)\b', text)
            for num in numbers:
                parsed = self.parse_number(num)
                if parsed:
                    return parsed
        except:
            pass
        return None

    def extract_hover_overlay_data(self, parent, test_mode=False, reel_id=None):
        likes = None
        comments = None
        debug_info = []
        
        try:
            overlay_text = parent.text
            overlay_lines = [line.strip() for line in overlay_text.split('\n') if line.strip()]
            
            if test_mode and reel_id:
                debug_info.append(f"      🔍 Overlay text for {reel_id}:")
                for line in overlay_lines[:10]:  # Show first 10 lines for debugging
                    debug_info.append(f"         '{line}'")
            
            # Look for likes
            for line in overlay_lines:
                line_lower = line.lower()
                
                # Check for "and X others" pattern
                if 'and' in line_lower and 'others' in line_lower and likes is None:
                    match = re.search(r'and\s+([\d,.]+[KMB]?)\s+others', line, re.IGNORECASE)
                    if match:
                        likes = self.parse_number(match.group(1))
                        if test_mode:
                            debug_info.append(f"      ✓ Found likes via 'and others': {likes}")
                
                # Check for direct "X likes" pattern
                if 'like' in line_lower and likes is None:
                    match = re.search(r'([\d,.]+[KMB]?)\s*like', line, re.IGNORECASE)
                    if match:
                        parsed = self.parse_number(match.group(1))
                        if parsed is not None:
                            likes = parsed
                            if test_mode:
                                debug_info.append(f"      ✓ Found likes directly: {likes}")
                
                # Check for comments
                if 'comment' in line_lower and comments is None:
                    # Try "View all X comments" pattern
                    view_all_match = re.search(r'view\s+all\s+([\d,.]+[KMB]?)\s+comment', line, re.IGNORECASE)
                    if view_all_match:
                        parsed = self.parse_number(view_all_match.group(1))
                        if parsed is not None:
                            comments = parsed
                            if test_mode:
                                debug_info.append(f"      ✓ Found comments via 'view all': {comments}")
                    else:
                        # Try direct "X comments" pattern
                        direct_match = re.search(r'([\d,.]+[KMB]?)\s+comment', line, re.IGNORECASE)
                        if direct_match:
                            parsed = self.parse_number(direct_match.group(1))
                            if parsed is not None:
                                comments = parsed
                                if test_mode:
                                    debug_info.append(f"      ✓ Found comments directly: {comments}")
                
                # Check for "0 comments" or "No comments" specifically
                if comments is None:
                    if re.search(r'\b0\s+comments?\b', line, re.IGNORECASE):
                        comments = 0
                        if test_mode:
                            debug_info.append(f"      ✓ Found explicit 0 comments")
                    elif re.search(r'\bno\s+comments?\b', line, re.IGNORECASE):
                        comments = 0
                        if test_mode:
                            debug_info.append(f"      ✓ Found 'no comments' - setting to 0")
            
            # If we still don't have values, look for standalone numbers
            if likes is None or comments is None:
                standalone_numbers = []
                for line in overlay_lines:
                    if re.match(r'^[\d,.]+[KMB]?$', line):
                        num = self.parse_number(line)
                        if num is not None:
                            standalone_numbers.append(num)
                
                if test_mode and standalone_numbers:
                    debug_info.append(f"      📊 Found standalone numbers: {standalone_numbers}")
                
                if len(standalone_numbers) >= 2:
                    if likes is None:
                        likes = standalone_numbers[0]
                        if test_mode:
                            debug_info.append(f"      ✓ Using first standalone as likes: {likes}")
                    if comments is None:
                        comments = standalone_numbers[1]
                        if test_mode:
                            debug_info.append(f"      ✓ Using second standalone as comments: {comments}")
                elif len(standalone_numbers) == 1:
                    if likes is None:
                        likes = standalone_numbers[0]
                        if test_mode:
                            debug_info.append(f"      ✓ Using only standalone as likes: {likes}")
            
            if test_mode:
                debug_info.append(f"      📈 Final extraction: likes={'N/A' if likes is None else likes}, comments={'N/A' if comments is None else comments}")
                
        except Exception as e:
            if test_mode:
                debug_info.append(f"      ❌ Error during extraction: {str(e)}")
        
        # Print debug info if in test mode
        if test_mode and debug_info:
            for line in debug_info:
                print(line)
        
        return likes, comments

    def hover_scrape_reels(self, driver, username, first_reel_id, max_reels=100, deep_scrape=False, test_mode=False):
        profile_url = f"https://www.instagram.com/{username}/reels/"
        driver.get(profile_url)
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        if test_mode:
            print(f"\n  🧪 STEP 2: Hover scrape validation (should start at {first_reel_id})...")
        else:
            print(f"  🎯 Step 2: Hover scraping for views/likes/comments (infinite scroll)...")
        
        # Find correct starting position
        max_scroll_up_attempts = 10
        for attempt in range(max_scroll_up_attempts):
            post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
            if post_links:
                first_visible_url = post_links[0].get_attribute('href')
                if first_visible_url and '/reel/' in first_visible_url:
                    first_visible_id = first_visible_url.split('/reel/')[-1].rstrip('/').split('?')[0]
                    if first_visible_id == first_reel_id:
                        if test_mode and attempt > 0:
                            print(f"    ✅ Found first reel after {attempt} scroll-ups")
                        break
                    else:
                        if test_mode and attempt == 0:
                            print(f"    ⚠️  First visible: {first_visible_id}, expected: {first_reel_id}")
                            print(f"    ⬆️  Scrolling up to find true first reel...")
                        driver.execute_script("window.scrollBy(0, -500);")
                        time.sleep(0.4)
            else:
                break
        
        cutoff_date = datetime.now() - timedelta(days=730)
        target_reels = 2000 if deep_scrape else max_reels
        hover_data = []
        processed_reel_ids = set()
        fail_counter = 0
        reached_cutoff = False
        
        while len(hover_data) < target_reels and fail_counter < 10 and not reached_cutoff:
            post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
            new_this_cycle = False
            
            for post_link in post_links:
                if len(hover_data) >= target_reels or reached_cutoff:
                    break
                
                try:
                    post_url = post_link.get_attribute('href')
                    if not post_url or '/reel/' not in post_url:
                        continue
                    
                    post_id = post_url.split('/reel/')[-1].rstrip('/').split('?')[0]
                    if post_id in processed_reel_ids:
                        continue
                    
                    is_visible = driver.execute_script(
                        "var rect = arguments[0].getBoundingClientRect();"
                        "return (rect.top >= 0 && rect.top < window.innerHeight - 100);",
                        post_link
                    )
                    
                    if not is_visible:
                        continue
                    
                    parent = post_link.find_element(By.XPATH, "..")
                    views = self.extract_views_from_container(parent)
                    
                    try:
                        actions = ActionChains(driver)
                        actions.move_to_element(parent).perform()
                        time.sleep(1.1)
                        likes, comments = self.extract_hover_overlay_data(
                            parent, 
                            test_mode=test_mode and len(hover_data) < max_reels, 
                            reel_id=post_id
                        )
                    except:
                        likes, comments = None, None
                    
                    if deep_scrape and len(hover_data) > 730:
                        print(f"    📅 Deep scrape reached approximate 2-year mark ({len(hover_data)} reels)")
                        reached_cutoff = True
                        break
                    
                    hover_data.append({
                        'reel_id': post_id,
                        'views': views,
                        'likes': likes,
                        'comments': comments,
                        'position': len(hover_data)
                    })
                    processed_reel_ids.add(post_id)
                    new_this_cycle = True
                    
                    if test_mode and len(hover_data) <= max_reels:
                        # Format output to distinguish N/A from 0
                        views_str = 'N/A' if views is None else str(views)
                        likes_str = 'N/A' if likes is None else str(likes)
                        comments_str = 'N/A' if comments is None else str(comments)
                        print(f"    [{len(hover_data)}] {post_id}: views={views_str}, likes={likes_str}, comments={comments_str}")
                    elif not test_mode and len(hover_data) % 25 == 0:
                        print(f"    Progress: {len(hover_data)}/{target_reels} reels")
                    
                    time.sleep(0.24)
                except Exception as e:
                    if test_mode:
                        print(f"    ❌ Error processing reel: {str(e)}")
                    continue
            
            if not new_this_cycle:
                fail_counter += 1
            else:
                fail_counter = 0
            
            driver.execute_script("window.scrollBy(0, 600);")
            time.sleep(0.7)
        
        if test_mode:
            print(f"\n  📊 Hover scrape complete: {len(hover_data)} reels")
        
        return hover_data

    def smart_merge_data(self, hover_data, arrow_data, test_mode=False):
        merged = []
        hover_lookup = {h['reel_id']: h for h in hover_data}
        
        for arrow_idx, arrow_reel in enumerate(arrow_data):
            arrow_id = arrow_reel['reel_id']
            hover_reel = hover_lookup.get(arrow_id)
            
            combined = {
                'reel_id': arrow_id,
                'position': arrow_idx + 1,
                'is_pinned': arrow_reel.get('is_pinned', False),
                'date': arrow_reel.get('date'),
                'date_display': arrow_reel.get('date_display'),
                'views': hover_reel.get('views') if hover_reel else None,
                'likes': hover_reel.get('likes') if hover_reel else arrow_reel.get('likes'),
                'comments': hover_reel.get('comments') if hover_reel else arrow_reel.get('comments'),
            }
            
            # Calculate engagement only if we have all required values
            if combined['views'] is not None and combined['likes'] is not None and combined['comments'] is not None:
                if combined['views'] > 0:  # Avoid division by zero
                    combined['engagement'] = round(((combined['likes'] + combined['comments']) / combined['views']) * 100, 2)
                else:
                    combined['engagement'] = None
            else:
                combined['engagement'] = None
            
            merged.append(combined)
        
        if test_mode:
            print(f"\n  📊 Merge complete:")
            print(f"     Total reels: {len(merged)}")
            print(f"\n  📋 Final merged reels (ALL {len(merged)} reels):")
            for i, reel in enumerate(merged, 1):
                pinned_marker = " 📌PINNED" if reel.get('is_pinned') else ""
                
                # Format values to distinguish N/A from 0
                views_str = 'N/A' if reel['views'] is None else str(reel['views'])
                likes_str = 'N/A' if reel['likes'] is None else str(reel['likes'])
                comments_str = 'N/A' if reel['comments'] is None else str(reel['comments'])
                engagement_str = 'N/A' if reel['engagement'] is None else f"{reel['engagement']}%"
                
                print(f"     {i}. {reel['reel_id']}{pinned_marker}")
                print(f"        Date: {reel['date_display'] or 'N/A'}")
                print(f"        Views: {views_str}, Likes: {likes_str}, Comments: {comments_str}")
                print(f"        Engagement: {engagement_str}")
        
        return merged

    def scrape_instagram_account(self, driver, username, max_reels=100, deep_scrape=False, test_mode=False):
        print(f"  👥 Getting exact follower count...")
        exact_followers = self.get_exact_follower_count(username)
        if exact_followers:
            print(f"  ✅ Exact follower count: {exact_followers:,}")
        else:
            print(f"  ⚠️  Could not get exact follower count via API, will try Selenium fallback...")
        
        arrow_data, pinned_count, need_fallback, early_termination = self.arrow_scrape_reels(
            driver, username, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode, use_main_profile=False
        )
        
        if need_fallback:
            print(f"\n  🔄 SWITCHING TO MAIN PROFILE for arrow scrape...")
            arrow_data, pinned_count, _, early_termination = self.arrow_scrape_reels(
                driver, username, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode, use_main_profile=True
            )
        
        # Track early termination
        if early_termination:
            self.early_terminations[username] = early_termination
        
        first_reel_id = arrow_data[0]['reel_id'] if arrow_data else None
        if not first_reel_id:
            print(f"  ❌ Arrow scrape failed - cannot proceed")
            return [], None, 0
        
        hover_data = self.hover_scrape_reels(driver, username, first_reel_id, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode)
        final_data = self.smart_merge_data(hover_data, arrow_data, test_mode=test_mode)
        
        if exact_followers:
            followers = exact_followers
        else:
            try:
                driver.get(f"https://www.instagram.com/{username}/")
                time.sleep(3)
                followers_elem = driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]/span")
                followers = followers_elem.get_attribute('title') or followers_elem.text
                followers = self.parse_number(followers.replace(',', ''))
                print(f"  ℹ️  Selenium fallback follower count: {followers:,}")
            except:
                followers = None
                print(f"  ⚠️  Could not retrieve follower count")
        
        if test_mode:
            print(f"\n  👥 Final Followers: {followers:,}" if followers else "\n  👥 Followers: N/A")
        
        return final_data, followers, pinned_count

    def load_existing_excel(self):
        import pandas as pd
        if os.path.exists(OUTPUT_EXCEL):
            try:
                excel_data = pd.read_excel(OUTPUT_EXCEL, sheet_name=None, index_col=0)
                return excel_data
            except:
                return {}
        return {}

    def create_dataframe_for_account(self, reels_data, followers, timestamp_col, existing_df=None):
        import pandas as pd
        if existing_df is not None and not existing_df.empty:
            df = existing_df.copy()
        else:
            df = pd.DataFrame()
        
        if timestamp_col not in df.columns:
            df[timestamp_col] = None
        
        df.loc["followers", timestamp_col] = followers
        df.loc["reels_scraped", timestamp_col] = len(reels_data)
        
        for reel in reels_data:
            reel_id = reel['reel_id']
            for metric in ['is_pinned', 'date', 'date_display', 'views', 'likes', 'comments', 'engagement']:
                row_name = f"reel_{reel_id}_{metric}"
                if row_name not in df.index:
                    df.loc[row_name] = None
                df.loc[row_name, timestamp_col] = reel.get(metric, "")
        
        return df

    def save_to_excel(self, all_account_data):
        import pandas as pd
        with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
            for username, df in all_account_data.items():
                sheet_name = username[:31]
                df.to_excel(writer, sheet_name=sheet_name)
        print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")

    def upload_to_google_drive(self):
        print("\n" + "="*70)
        print("☁️  Uploading to Google Drive...")
        print("="*70)
        try:
            result = subprocess.run(['rclone', 'version'], 
                capture_output=True, 
                text=True)
            if result.returncode != 0:
                print("❌ rclone not found. Please install rclone first.")
                print("   Visit: https://rclone.org/downloads/")
                return False
            
            excel_path = os.path.abspath(OUTPUT_EXCEL)
            print(f"\n📤 Uploading {OUTPUT_EXCEL}...")
            upload_result = subprocess.run(
                ['rclone', 'copy', excel_path, 'gdrive:', '--update', '-v'],
                capture_output=True,
                text=True
            )
            
            if upload_result.returncode == 0:
                print("✅ Successfully uploaded to Google Drive!")
                print("📁 File ID: 19PDIP7_YaluxsmvQsDJ89Bn5JkXnK2n2")
                print("🌐 View at: https://crespo.world/crespomize.html")
                return True
            else:
                print(f"❌ Upload failed: {upload_result.stderr}")
                return False
        except FileNotFoundError:
            print("❌ rclone not found. Please install rclone first.")
            print("   Visit: https://rclone.org/downloads/")
            return False
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return False

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
            print(f"  Reels scraped: {termination_info['reels_scraped']}")
            
            if termination_info.get('last_date'):
                days_ago = (datetime.now() - termination_info['last_date']).days
                print(f"  Went back: ~{days_ago} days")
        
        retry = input("\n🔄 Would you like to try to get more posts from these accounts? (y/n): ").strip().lower()
        
        if retry == 'y':
            print("\n🔄 Attempting to get more posts...")
            for username in self.early_terminations.keys():
                print(f"\n📱 Re-attempting @{username}...")
                try:
                    # Try with increased timeout and different strategy
                    reels_data, followers, pinned_count = self.scrape_instagram_account(
                        self.driver, username, 
                        max_reels=2000,  # Try to get more
                        deep_scrape=True, 
                        test_mode=False
                    )
                    
                    if len(reels_data) > self.early_terminations[username]['reels_scraped']:
                        print(f"  ✅ Got {len(reels_data) - self.early_terminations[username]['reels_scraped']} additional reels!")
                        existing_df = all_account_data.get(username)
                        df = self.create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
                        all_account_data[username] = df
                    else:
                        print(f"  ℹ️  No additional reels found - likely reached account limit")
                except Exception as e:
                    print(f"  ❌ Re-attempt failed: {e}")

    def get_scrape_mode(self):
        print("\n" + "="*70)
        print("🎯 SELECT SCRAPE MODE")
        print("="*70)
        print("\n1. Custom number of posts (default: 100)")
        print("2. Deep scrape (back 2 years or to beginning of account)")
        print("3. Test mode (15 reels on @popdartsgame, displays all 15)")
        print()
        while True:
            choice = input("Enter your choice (1, 2, or 3): ").strip()
            if choice == '1' or choice == '':
                num_input = input("\nHow many posts per account? (default 100): ").strip()
                try:
                    num_posts = int(num_input) if num_input else 100
                    if num_posts > 0:
                        return num_posts, False, False
                    else:
                        print("Please enter a positive number.")
                except ValueError:
                    print("Invalid input. Using default: 100")
                    return 100, False, False
            elif choice == '2':
                confirm = input("\n⚠️  Deep scrape will go back 2 years or to the beginning of the account. This may take a while. Continue? (y/n): ").strip().lower()
                if confirm == 'y':
                    return None, True, False
                else:
                    continue
            elif choice == '3':
                return 15, False, True
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def run(self):
        """Main execution function"""
        import pandas as pd
        
        self.ensure_packages()
        
        print("\n" + "="*70)
        print("📸 Instagram Reels Analytics Tracker v3.0")
        print("="*70)
        
        browser_choice = self.select_browser()
        max_reels, deep_scrape, test_mode = self.get_scrape_mode()
        
        if test_mode:
            print("\n🧪 TEST MODE ACTIVATED")
            print(f"   Account: @popdartsgame")
            print(f"   Reels: 15 (will display all 15)")
            print(f"   Browser: {browser_choice.upper()}")
            print(f"   Output: Terminal only (no Excel file)")
            print(f"   Strategy: Arrow FIRST → Hover SECOND → Merge")
            print(f"   Debug: Enhanced hover scrape debug info enabled")
            accounts = ["popdartsgame"]
            expected_reels = 15
        else:
            print(f"\n✅ Will scrape {len(ACCOUNTS_TO_TRACK)} account(s):\n")
            for i, account in enumerate(ACCOUNTS_TO_TRACK, 1):
                print(f"   {i}. @{account}")
            print(f"\n   Browser: {browser_choice.upper()}")
            accounts = ACCOUNTS_TO_TRACK
            if deep_scrape:
                print("\n🔍 Mode: DEEP SCRAPE (back 2 years or to beginning of account)")
                expected_reels = None
            else:
                print(f"\n📊 Mode: {max_reels} posts per account")
                expected_reels = max_reels
        
        input("\n▶️  Press ENTER to start scraping...")
        
        self.driver = self.setup_driver(browser=browser_choice)
        existing_data = self.load_existing_excel() if not test_mode else {}
        timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_account_data = {}
        scrape_results = {}
        
        try:
            for idx, username in enumerate(accounts, 1):
                print("\n" + "="*70)
                if test_mode:
                    print(f"🧪 TEST SCRAPE: @{username}")
                else:
                    print(f"📱 [{idx}/{len(accounts)}] Processing @{username}")
                print("="*70)
                
                try:
                    reels_data, followers, pinned_count = self.scrape_instagram_account(
                        self.driver, username, max_reels=max_reels or 100, deep_scrape=deep_scrape, test_mode=test_mode
                    )
                    
                    scrape_results[username] = {
                        'reels_count': len(reels_data),
                        'followers': followers,
                        'pinned_count': pinned_count,
                        'deep_scrape': deep_scrape
                    }
                    
                    # Store current data for backup
                    if not test_mode:
                        existing_df = existing_data.get(username, pd.DataFrame())
                        df = self.create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
                        all_account_data[username] = df
                        self.current_data = all_account_data
                    
                    if test_mode:
                        print("\n" + "="*70)
                        print("✅ TEST COMPLETE!")
                        print("="*70)
                        print(f"\n📊 Summary:")
                        print(f"   Account: @{username}")
                        print(f"   Browser: {browser_choice.upper()}")
                        print(f"   Followers: {followers:,}" if followers else "   Followers: N/A")
                        print(f"   Reels scraped: {len(reels_data)} (including {pinned_count} pinned)")
                        print(f"   Pinned posts: {pinned_count}")
                    else:
                        print(f"\n  ✅ @{username} complete!")
                        print(f"  👥 Followers: {followers:,}" if followers else "  👥 Followers: N/A")
                        if deep_scrape:
                            if reels_data:
                                oldest_date = None
                                for reel in reversed(reels_data):
                                    if reel.get('date_timestamp'):
                                        oldest_date = reel['date_timestamp']
                                        break
                                if oldest_date:
                                    days_back = (datetime.now() - oldest_date).days
                                    print(f"  🎬 Reels: {len(reels_data)} (spanning ~{days_back} days, {pinned_count} pinned)")
                                else:
                                    print(f"  🎬 Reels: {len(reels_data)} (including {pinned_count} pinned)")
                            else:
                                print(f"  🎬 Reels: 0")
                        else:
                            print(f"  🎬 Reels: {len(reels_data)}/{expected_reels if expected_reels else 'N/A'} (including {pinned_count} pinned)")
                
                except Exception as e:
                    print(f"\n  ❌ Error with @{username}: {e}")
                    traceback.print_exc()
                    scrape_results[username] = {
                        'reels_count': 0,
                        'followers': None,
                        'pinned_count': 0,
                        'deep_scrape': deep_scrape
                    }
                    continue
            
            if not test_mode:
                # Save initial results
                self.save_to_excel(all_account_data)
                self.upload_to_google_drive()
                
                # Handle early terminations
                if self.early_terminations:
                    self.handle_early_terminations(all_account_data, timestamp_col)
                    # Save updated results
                    self.save_to_excel(all_account_data)
                    self.upload_to_google_drive()
                
                print("\n" + "="*70)
                print("✅ All scraping complete!")
                print(f"📁 Local file: '{OUTPUT_EXCEL}'")
                print(f"🌐 View analytics: https://crespo.world/crespomize.html")
                
                # Show early termination summary if any
                if self.early_terminations:
                    print("\n⚠️  Early terminations:")
                    for username, info in self.early_terminations.items():
                        print(f"  @{username}: Stopped at {info['reels_scraped']} reels")
                
                print("="*70 + "\n")
        
        finally:
            if self.driver:
                self.driver.quit()

    # Methods for master scraper integration
    def scrape_recent_posts(self, account, limit=30):
        """Scrape recent posts for master scraper (test mode)"""
        if not self.driver:
            self.driver = self.setup_driver()
        
        reels_data, followers, pinned_count = self.scrape_instagram_account(
            self.driver, account, max_reels=limit, deep_scrape=False, test_mode=False
        )
        
        # Convert to format expected by master scraper
        posts = []
        for reel in reels_data:
            posts.append({
                'id': reel['reel_id'],
                'url': f"https://www.instagram.com/reel/{reel['reel_id']}/",
                'caption': '',  # Would need additional scraping
                'like_count': reel.get('likes', 0),
                'comment_count': reel.get('comments', 0),
                'timestamp': reel.get('date'),
                'media_type': 'VIDEO'
            })
        
        return posts
    
    def scrape_by_date(self, account, start_date):
        """Scrape posts from a specific date for master scraper"""
        if not self.driver:
            self.driver = self.setup_driver()
        
        # Determine if this is deep scrape based on date
        days_back = (datetime.now() - start_date).days
        deep_scrape = days_back > 365  # Deep scrape if more than a year
        
        reels_data, followers, pinned_count = self.scrape_instagram_account(
            self.driver, account, max_reels=2000, deep_scrape=deep_scrape, test_mode=False
        )
        
        # Filter by date and convert to format expected by master scraper
        posts = []
        for reel in reels_data:
            if reel.get('date_timestamp'):
                if reel['date_timestamp'] >= start_date:
                    posts.append({
                        'id': reel['reel_id'],
                        'url': f"https://www.instagram.com/reel/{reel['reel_id']}/",
                        'caption': '',
                        'like_count': reel.get('likes', 0),
                        'comment_count': reel.get('comments', 0),
                        'timestamp': reel.get('date'),
                        'media_type': 'VIDEO'
                    })
        
        return posts


if __name__ == "__main__":
    scraper = InstagramScraper()
    scraper.run()
