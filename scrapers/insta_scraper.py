#!/usr/bin/env python3
"""
Instagram Reels Analytics Tracker v4.0
- Hover-first mode - hover scrape runs first, then individual URL scrape for dates
- Cross-validation between hover and URL data with outlier detection
- Logarithmic correlation-based outlier resolution (uses views-likes relationship)
- Auto-detection when running out of posts (no more infinite waiting)
- Interrupt handler (Ctrl+C saves backup file)
- Master scraper integration support
- Updates Excel with separate tabs per account
- Auto-uploads to Google Drive
- Deep scrape goes back 2 years or to beginning of account
- Better debugging for hover scrape comment extraction
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
import statistics
import math
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
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

# Login credentials for Instagram
INSTAGRAM_USERNAME = "crespoworld"
INSTAGRAM_PASSWORD = "deleteme"

class InstagramScraper:
    # Cross-validation outlier threshold (percentage difference to flag as outlier)
    OUTLIER_THRESHOLD_PCT = 20.0
    
    def __init__(self):
        self.driver = None
        self.interrupted = False
        self.current_data = {}
        self.early_terminations = {}  # Track any early terminations
        
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

    def dismiss_modal(self, driver, max_attempts=3):
        """
        Dismiss Instagram login/signup modal by clicking X button.
        Returns True if modal was dismissed, False otherwise.
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        
        print("  🔍 Checking for login modal...")
        
        for attempt in range(max_attempts):
            try:
                # Common selectors for the X/close button on Instagram modals
                close_button_selectors = [
                    # SVG close button (most common)
                    "//div[@role='dialog']//button[contains(@class, 'xqui')]//*[name()='svg']/..",
                    "//div[@role='dialog']//button/*[name()='svg' and @aria-label='Close']/..",
                    # Close button with aria-label
                    "//button[@aria-label='Close']",
                    "//div[@role='button' and @aria-label='Close']",
                    # Generic close button in dialog
                    "//div[@role='dialog']//div[@role='button'][1]",
                    "//div[@role='dialog']//button[1]",
                    # Not now button (alternative to close)
                    "//button[contains(text(), 'Not Now')]",
                    "//button[contains(text(), 'Not now')]",
                    "//div[contains(text(), 'Not Now')]",
                    "//div[contains(text(), 'Not now')]",
                ]
                
                for selector in close_button_selectors:
                    try:
                        close_btn = driver.find_element(By.XPATH, selector)
                        if close_btn.is_displayed():
                            close_btn.click()
                            print(f"  ✅ Modal dismissed (attempt {attempt + 1})")
                            time.sleep(1.5)
                            return True
                    except (NoSuchElementException, Exception):
                        continue
                
                # If no button found, check if dialog still exists
                try:
                    dialog = driver.find_element(By.XPATH, "//div[@role='dialog']")
                    if dialog.is_displayed():
                        # Try pressing Escape key
                        from selenium.webdriver.common.keys import Keys
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        print(f"  ✅ Modal dismissed with Escape key (attempt {attempt + 1})")
                        time.sleep(1.5)
                        return True
                except NoSuchElementException:
                    # No dialog found, we're good
                    print("  ✅ No modal present")
                    return True
                
                time.sleep(1)
                
            except Exception as e:
                print(f"  ⚠️ Error dismissing modal (attempt {attempt + 1}): {e}")
                time.sleep(1)
        
        print("  ⚠️ Could not dismiss modal after all attempts")
        return False

    def login_to_instagram(self, driver):
        """
        Log in to Instagram using credentials.
        Returns True if login successful, False otherwise.
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        
        print("  🔐 Attempting to log in to Instagram...")
        
        try:
            # Navigate to login page
            driver.get("https://www.instagram.com/accounts/login/")
            time.sleep(3)
            
            # Dismiss any cookie consent dialogs
            try:
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Allow') or contains(text(), 'Accept')]")
                for btn in cookie_buttons:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
                        break
            except:
                pass
            
            # Find and fill username field
            try:
                username_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                username_field.clear()
                username_field.send_keys(INSTAGRAM_USERNAME)
                time.sleep(0.5)
            except TimeoutException:
                print("  ❌ Could not find username field")
                return False
            
            # Find and fill password field
            try:
                password_field = driver.find_element(By.NAME, "password")
                password_field.clear()
                password_field.send_keys(INSTAGRAM_PASSWORD)
                time.sleep(0.5)
            except NoSuchElementException:
                print("  ❌ Could not find password field")
                return False
            
            # Click login button
            try:
                login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                print("  ⏳ Waiting for login...")
                time.sleep(5)
            except NoSuchElementException:
                print("  ❌ Could not find login button")
                return False
            
            # Check if login was successful (look for profile icon or home feed)
            try:
                # Wait for redirect and check for logged-in elements
                time.sleep(3)
                
                # Check if we're still on login page (error)
                if "/accounts/login" in driver.current_url:
                    print("  ❌ Login failed - still on login page")
                    return False
                
                # Dismiss any "Save Login Info" or "Turn on Notifications" popups
                self.dismiss_modal(driver, max_attempts=2)
                
                print("  ✅ Login successful!")
                return True
                
            except Exception as e:
                print(f"  ⚠️ Login verification error: {e}")
                return False
            
        except Exception as e:
            print(f"  ❌ Login error: {e}")
            return False

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
        
        # Try to add cookies first
        print("  🍪 Attempting to load cookies...")
        cookies_loaded = False
        try:
            for cookie in INSTAGRAM_COOKIES:
                driver.add_cookie(cookie)
            driver.refresh()
            time.sleep(3)
            cookies_loaded = True
        except Exception as e:
            print(f"  ⚠️ Could not load cookies: {e}")
        
        # Dismiss any login modals that appear
        self.dismiss_modal(driver, max_attempts=3)
        
        # Check if we're logged in (look for login form or profile elements)
        logged_in = False
        try:
            # If we can see the login button/form, we're not logged in
            login_elements = driver.find_elements(By.XPATH, "//button[contains(text(), 'Log in') or contains(text(), 'Log In')]")
            if not login_elements or not any(el.is_displayed() for el in login_elements):
                # Check for logged-in indicators
                profile_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/direct/') or contains(@href, '/accounts/')]")
                if profile_links:
                    logged_in = True
                    print("  ✅ Already logged in via cookies!")
        except:
            pass
        
        # If not logged in, try to log in with credentials
        if not logged_in:
            print("  ⚠️ Not logged in with cookies, attempting login with credentials...")
            if self.login_to_instagram(driver):
                logged_in = True
            else:
                print("  ⚠️ Login failed, will try to scrape as guest (limited data)")
                # Dismiss any remaining modals
                self.dismiss_modal(driver, max_attempts=2)
        
        # Final modal dismissal after everything is set up
        time.sleep(2)
        self.dismiss_modal(driver, max_attempts=2)
        
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

    def hover_scrape_reels(self, driver, username, first_reel_id=None, max_reels=100, deep_scrape=False, deep_deep=False, test_mode=False):
        profile_url = f"https://www.instagram.com/{username}/reels/"
        driver.get(profile_url)
        time.sleep(5)
        
        # Dismiss any login modals that appear when navigating to the profile
        self.dismiss_modal(driver, max_attempts=2)
        
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        
        if test_mode:
            if first_reel_id:
                print(f"\n  🧪 STEP 2: Hover scrape validation (should start at {first_reel_id})...")
            else:
                print(f"\n  🧪 STEP 1: Hover scrape (extracting views, likes, comments, URLs)...")
        else:
            if first_reel_id:
                print(f"  🎯 Step 2: Hover scraping for views/likes/comments (infinite scroll)...")
            else:
                print(f"  🎯 Step 1: Hover scraping for views/likes/comments/URLs...")
        
        # Find correct starting position (only if first_reel_id is provided for validation)
        if first_reel_id:
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
        # deep_deep means no limit, deep_scrape (without deep_deep) means 2 years (~730 posts)
        if deep_deep:
            target_reels = 99999  # Essentially unlimited for deep deep
        elif deep_scrape:
            target_reels = 2000  # Cap at 2000 for 2-year deep scrape
        else:
            target_reels = max_reels
        
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
                    
                    # Apply 2-year cutoff only for deep_scrape (not deep_deep)
                    if deep_scrape and not deep_deep and len(hover_data) > 730:
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

    def scrape_individual_urls(self, driver, hover_data, test_mode=False):
        """
        Visit each individual reel URL to extract date information and validate likes.
        This is used as an alternative to arrow scraping for getting dates.
        """
        if test_mode:
            print(f"\n  🧪 STEP 2: Individual URL scrape (extracting dates from {len(hover_data)} URLs)...")
        else:
            print(f"  📅 Step 2: Individual URL scraping for dates...")
        
        url_data = []
        modal_dismissed_count = 0  # Track if we've dismissed modals for first few URLs
        
        for idx, reel in enumerate(hover_data):
            reel_id = reel.get('reel_id')
            if not reel_id:
                continue
            
            reel_url = f"https://www.instagram.com/reel/{reel_id}/"
            
            try:
                driver.get(reel_url)
                time.sleep(2)
                
                # Dismiss modal for first few URLs (they typically only appear initially)
                if modal_dismissed_count < 3:
                    if self.dismiss_modal(driver, max_attempts=1):
                        modal_dismissed_count += 1
                
                data = {
                    'reel_id': reel_id,
                    'date': None,
                    'date_display': None,
                    'date_timestamp': None,
                    'likes': None,
                    'comments': None,
                }
                
                # Extract date
                try:
                    time_elements = driver.find_elements(By.TAG_NAME, "time")
                    if time_elements:
                        time_elem = time_elements[0]
                        data['date'] = time_elem.get_attribute('datetime')
                        data['date_display'] = time_elem.text
                        data['date_timestamp'] = self.parse_date_to_timestamp(data['date'])
                except Exception:
                    pass
                
                # Extract likes for validation
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    others_match = re.search(r'and\s+([\d,.]+[KMB]?)\s+others', body_text, re.IGNORECASE)
                    if others_match:
                        data['likes'] = self.parse_number(others_match.group(1))
                    else:
                        like_match = re.search(r'([\d,.]+[KMB]?)\s+likes?', body_text, re.IGNORECASE)
                        if like_match:
                            data['likes'] = self.parse_number(like_match.group(1))
                except Exception:
                    pass
                
                # Extract comments for validation
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
                except Exception:
                    pass
                
                url_data.append(data)
                
                if test_mode:
                    date_str = data.get('date_display', 'N/A') or 'N/A'
                    likes_str = 'N/A' if data['likes'] is None else str(data['likes'])
                    comments_str = 'N/A' if data['comments'] is None else str(data['comments'])
                    print(f"    [{idx+1}/{len(hover_data)}] {reel_id}: date={date_str}, likes={likes_str}, comments={comments_str}")
                elif (idx + 1) % 10 == 0:
                    print(f"    Progress: {idx+1}/{len(hover_data)} URLs scraped...")
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                if test_mode:
                    print(f"    ❌ Error scraping URL {reel_id}: {str(e)}")
                url_data.append({
                    'reel_id': reel_id,
                    'date': None,
                    'date_display': None,
                    'date_timestamp': None,
                    'likes': None,
                    'comments': None,
                })
                continue
        
        if test_mode:
            print(f"\n  📊 Individual URL scrape complete: {len(url_data)} URLs processed")
        
        return url_data

    def cross_validate_data(self, hover_data, url_data, test_mode=False):
        """
        Cross-validate data between hover scrape and individual URL scrape.
        Identifies outliers where likes or comments differ significantly.
        Uses logarithmic correlation between views and likes to determine which value is more accurate.
        """
        if test_mode:
            print(f"\n  🔍 STEP 3: Cross-validating data...")
        else:
            print(f"  🔍 Step 3: Cross-validating data...")
        
        url_lookup = {u['reel_id']: u for u in url_data}
        outliers = []
        
        # First, collect all valid views-likes pairs for correlation analysis
        valid_pairs = []
        for hover_reel in hover_data:
            reel_id = hover_reel.get('reel_id')
            url_reel = url_lookup.get(reel_id)
            
            views = hover_reel.get('views')
            # Use hover_likes as the baseline since we trust hover scrape
            hover_likes = hover_reel.get('likes')
            url_likes = url_reel.get('likes') if url_reel else None
            
            # For correlation, only use pairs where hover and URL agree (not outliers)
            if views is not None and views > 0 and hover_likes is not None and hover_likes > 0:
                if url_likes is not None and url_likes > 0:
                    # Check if they roughly agree (within threshold)
                    max_likes = max(hover_likes, url_likes)
                    diff_pct = abs(hover_likes - url_likes) / max_likes * 100
                    if diff_pct <= self.OUTLIER_THRESHOLD_PCT:
                        valid_pairs.append((views, hover_likes))
                else:
                    # If no URL likes, assume hover is correct
                    valid_pairs.append((views, hover_likes))
        
        # Calculate logarithmic regression coefficients if we have enough data
        # log(likes) = a * log(views) + b
        log_a, log_b = None, None
        if len(valid_pairs) >= 3:
            try:
                # Filter to ensure all values are > 0 for logarithm
                safe_pairs = [(v, l) for v, l in valid_pairs if v > 0 and l > 0]
                if len(safe_pairs) >= 3:
                    log_views = [math.log(v) for v, l in safe_pairs]
                    log_likes = [math.log(l) for v, l in safe_pairs]
                    
                    n = len(safe_pairs)
                    sum_x = sum(log_views)
                    sum_y = sum(log_likes)
                    sum_xy = sum(x * y for x, y in zip(log_views, log_likes))
                    sum_xx = sum(x * x for x in log_views)
                    
                    denominator = n * sum_xx - sum_x * sum_x
                    if denominator != 0:
                        log_a = (n * sum_xy - sum_x * sum_y) / denominator
                        log_b = (sum_y - log_a * sum_x) / n
                        
                        if test_mode:
                            print(f"  📈 Logarithmic correlation: log(likes) = {log_a:.3f} * log(views) + {log_b:.3f}")
            except Exception as e:
                if test_mode:
                    print(f"  ⚠️  Could not calculate log correlation: {e}")
        
        # Collect differences for statistical analysis
        likes_diffs = []
        comments_diffs = []
        
        for hover_reel in hover_data:
            reel_id = hover_reel.get('reel_id')
            url_reel = url_lookup.get(reel_id)
            
            if not url_reel:
                continue
            
            hover_likes = hover_reel.get('likes')
            url_likes = url_reel.get('likes')
            hover_comments = hover_reel.get('comments')
            url_comments = url_reel.get('comments')
            views = hover_reel.get('views')
            
            # Calculate differences (as percentages) when both values exist
            # Use max of both values as denominator for more robust comparison
            if hover_likes is not None and url_likes is not None:
                max_likes = max(hover_likes, url_likes)
                if max_likes > 0:
                    diff_pct = abs(hover_likes - url_likes) / max_likes * 100
                    likes_diffs.append((reel_id, hover_likes, url_likes, diff_pct, 'likes', views))
            
            if hover_comments is not None and url_comments is not None:
                max_comments = max(hover_comments, url_comments)
                if max_comments > 0:
                    diff_pct = abs(hover_comments - url_comments) / max_comments * 100
                    comments_diffs.append((reel_id, hover_comments, url_comments, diff_pct, 'comments', views))
        
        # Identify outliers using class threshold constant and resolve using log correlation
        for reel_id, hover_val, url_val, diff_pct, metric_type, views in likes_diffs:
            if diff_pct > self.OUTLIER_THRESHOLD_PCT:
                # Determine which value is more likely correct using logarithmic correlation
                best_value = None
                selection_reason = ""
                
                if log_a is not None and log_b is not None and views is not None and views > 0:
                    try:
                        # Predict expected likes from views using log correlation
                        expected_log_likes = log_a * math.log(views) + log_b
                        # Prevent overflow for very large expected values
                        if expected_log_likes > 100:  # exp(100) is astronomical
                            expected_log_likes = 100
                        expected_likes = math.exp(expected_log_likes)
                        
                        # Calculate how far each value is from expected (safe logarithm)
                        hover_distance = abs(math.log(max(hover_val, 1)) - expected_log_likes) if hover_val is not None else float('inf')
                        url_distance = abs(math.log(max(url_val, 1)) - expected_log_likes) if url_val is not None else float('inf')
                        
                        if hover_distance < url_distance:
                            best_value = hover_val
                            selection_reason = f"closer to expected ({int(expected_likes):,})"
                        else:
                            best_value = url_val
                            selection_reason = f"closer to expected ({int(expected_likes):,})"
                    except (ValueError, OverflowError):
                        # Fallback on math errors
                        best_value = max(hover_val, url_val) if hover_val and url_val else (hover_val or url_val)
                        selection_reason = "higher value (math error fallback)"
                else:
                    # Fallback: use the higher value (usually more accurate)
                    best_value = max(hover_val, url_val) if hover_val and url_val else (hover_val or url_val)
                    selection_reason = "higher value (fallback)"
                
                outliers.append({
                    'reel_id': reel_id,
                    'metric': metric_type,
                    'hover_value': hover_val,
                    'url_value': url_val,
                    'diff_percent': round(diff_pct, 1),
                    'best_value': best_value,
                    'selection_reason': selection_reason
                })
        
        for reel_id, hover_val, url_val, diff_pct, metric_type, views in comments_diffs:
            if diff_pct > self.OUTLIER_THRESHOLD_PCT:
                # For comments, use the higher value as they're less predictable
                best_value = max(hover_val, url_val) if hover_val and url_val else (hover_val or url_val)
                selection_reason = "higher value"
                
                outliers.append({
                    'reel_id': reel_id,
                    'metric': metric_type,
                    'hover_value': hover_val,
                    'url_value': url_val,
                    'diff_percent': round(diff_pct, 1),
                    'best_value': best_value,
                    'selection_reason': selection_reason
                })
        
        # Display outliers in terminal
        if outliers:
            print(f"\n  ⚠️  OUTLIERS DETECTED ({len(outliers)} discrepancies found):")
            print("  " + "-" * 70)
            for outlier in outliers:
                print(f"    📍 {outlier['reel_id']}")
                print(f"       {outlier['metric'].capitalize()}: hover={outlier['hover_value']}, url={outlier['url_value']} ({outlier['diff_percent']}% diff)")
                print(f"       → Using {outlier['best_value']:,} ({outlier['selection_reason']})")
            print("  " + "-" * 70)
            print(f"  📊 Outlier values resolved using logarithmic views-likes correlation")
        else:
            print(f"  ✅ No significant outliers detected - data is consistent")
        
        # Calculate and display statistics
        if likes_diffs:
            all_likes_diff_pcts = [d[3] for d in likes_diffs]
            avg_likes_diff = statistics.mean(all_likes_diff_pcts) if all_likes_diff_pcts else 0
            if test_mode:
                print(f"\n  📈 Likes validation: avg diff = {avg_likes_diff:.1f}%")
        
        if comments_diffs:
            all_comments_diff_pcts = [d[3] for d in comments_diffs]
            avg_comments_diff = statistics.mean(all_comments_diff_pcts) if all_comments_diff_pcts else 0
            if test_mode:
                print(f"  📈 Comments validation: avg diff = {avg_comments_diff:.1f}%")
        
        return outliers

    def smart_merge_data_v2(self, hover_data, url_data, outliers, test_mode=False):
        """
        Merge hover scrape and individual URL scrape data.
        Uses URL data for dates, and uses best_value from outlier analysis for outliers.
        """
        merged = []
        url_lookup = {u['reel_id']: u for u in url_data}
        
        # Build outlier lookup with best values
        outlier_lookup = {}
        for o in outliers:
            reel_id = o['reel_id']
            if reel_id not in outlier_lookup:
                outlier_lookup[reel_id] = {}
            outlier_lookup[reel_id][o['metric']] = o['best_value']
        
        for idx, hover_reel in enumerate(hover_data):
            reel_id = hover_reel.get('reel_id')
            url_reel = url_lookup.get(reel_id, {})
            reel_outliers = outlier_lookup.get(reel_id, {})
            
            # Use outlier best_value if available, otherwise use hover data
            likes = reel_outliers.get('likes') if 'likes' in reel_outliers else hover_reel.get('likes')
            comments = reel_outliers.get('comments') if 'comments' in reel_outliers else hover_reel.get('comments')
            
            combined = {
                'reel_id': reel_id,
                'position': idx + 1,
                'is_pinned': False,  # Will be detected separately if needed
                'date': url_reel.get('date'),
                'date_display': url_reel.get('date_display'),
                'views': hover_reel.get('views'),
                'likes': likes,
                'comments': comments,
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
            print(f"\n  📊 Merge complete (hover-first method with log correlation):")
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

    def scrape_instagram_account(self, driver, username, max_reels=100, deep_scrape=False, deep_deep=False, test_mode=False):
        """
        Main scraping method using hover-first approach.
        Hover scrape first, then individual URL scraping for dates.
        """
        print(f"  👥 Getting exact follower count...")
        exact_followers = self.get_exact_follower_count(username)
        if exact_followers:
            print(f"  ✅ Exact follower count: {exact_followers:,}")
        else:
            print(f"  ⚠️  Could not get exact follower count via API, will try Selenium fallback...")
        
        # Hover-first approach
        # Step 1: Hover scrape to get views, likes, comments, URLs
        hover_data = self.hover_scrape_reels(driver, username, first_reel_id=None, max_reels=max_reels, deep_scrape=deep_scrape, deep_deep=deep_deep, test_mode=test_mode)
        
        if not hover_data:
            print(f"  ❌ Hover scrape failed - cannot proceed")
            return [], None, 0
        
        # Step 2: Individual URL scrape to get dates
        url_data = self.scrape_individual_urls(driver, hover_data, test_mode=test_mode)
        
        # Step 3: Cross-validate data and identify outliers (with log correlation)
        outliers = self.cross_validate_data(hover_data, url_data, test_mode=test_mode)
        
        # Step 4: Merge data using best values from outlier analysis
        final_data = self.smart_merge_data_v2(hover_data, url_data, outliers, test_mode=test_mode)
        pinned_count = 0  # Pinned detection not available in hover-first mode
        
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

    def get_scrape_mode(self):
        print("\n" + "="*70)
        print("🎯 SELECT SCRAPE MODE")
        print("="*70)
        print("\n1. Custom scrape (default: 100 posts)")
        print("2. Deep scrape (back 2 years)")
        print("3. Test mode (15 reels on @popdartsgame)")
        print()
        while True:
            choice = input("Enter your choice (1, 2, or 3): ").strip()
            if choice == '1' or choice == '':
                num_input = input("\nHow many posts per account? (default 100): ").strip()
                try:
                    num_posts = int(num_input) if num_input else 100
                    if num_posts > 0:
                        return num_posts, False, False, False  # Added 4th return value for deep_deep
                    else:
                        print("Please enter a positive number.")
                except ValueError:
                    print("Invalid input. Using default: 100")
                    return 100, False, False, False
            elif choice == '2':
                print("\n⚠️  Deep scrape options:")
                print("   a) 2 years back (default)")
                print("   b) All the way back (DEEP DEEP - takes significantly longer)")
                deep_choice = input("\nEnter 'a' for 2 years or 'b' for all the way back (default=a): ").strip().lower()
                
                if deep_choice == 'b':
                    confirm = input("\n🔥 DEEP DEEP mode will scrape ALL available posts. This takes significantly longer. Continue? (y/n): ").strip().lower()
                    if confirm == 'y':
                        print("  ✅ Deep deep mode selected - will scrape ALL available posts!")
                        return None, True, False, True  # deep_scrape=True, deep_deep=True
                    else:
                        continue
                else:
                    confirm = input("\n⚠️  Deep scrape will go back 2 years. Continue? (y/n): ").strip().lower()
                    if confirm == 'y':
                        print("  ✅ Deep mode selected - will scrape back 2 years")
                        return None, True, False, False  # deep_scrape=True, deep_deep=False
                    else:
                        continue
            elif choice == '3':
                return 15, False, True, False
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

    def run(self):
        """Main execution function"""
        import pandas as pd
        
        self.ensure_packages()
        
        print("\n" + "="*70)
        print("📸 Instagram Reels Analytics Tracker v4.0")
        print("="*70)
        
        browser_choice = self.select_browser()
        max_reels, deep_scrape, test_mode, deep_deep = self.get_scrape_mode()
        
        if test_mode:
            print("\n🧪 TEST MODE ACTIVATED")
            print(f"   Account: @popdartsgame")
            print(f"   Reels: 15 (will display all 15)")
            print(f"   Browser: {browser_choice.upper()}")
            print(f"   Output: Terminal only (no Excel file)")
            print(f"   Strategy: Hover FIRST → URL SECOND → Cross-validate → Merge")
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
                if deep_deep:
                    print("\n🔥 Mode: DEEP DEEP SCRAPE (ALL available posts - no limit)")
                else:
                    print("\n🔍 Mode: DEEP SCRAPE (back 2 years)")
                expected_reels = None
            else:
                print(f"\n📊 Mode: {max_reels} posts per account")
                expected_reels = max_reels
            print("   Strategy: Hover FIRST → URL SECOND → Cross-validate → Merge")
        
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
                        self.driver, username, max_reels=max_reels or 100, deep_scrape=deep_scrape, deep_deep=deep_deep, test_mode=test_mode
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
                        print(f"   Reels scraped: {len(reels_data)}")
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
                                    print(f"  🎬 Reels: {len(reels_data)} (spanning ~{days_back} days)")
                                else:
                                    print(f"  🎬 Reels: {len(reels_data)}")
                            else:
                                print(f"  🎬 Reels: 0")
                        else:
                            print(f"  🎬 Reels: {len(reels_data)}/{expected_reels if expected_reels else 'N/A'}")
                
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
                # Save results
                self.save_to_excel(all_account_data)
                self.upload_to_google_drive()
                
                print("\n" + "="*70)
                print("✅ All scraping complete!")
                print(f"📁 Local file: '{OUTPUT_EXCEL}'")
                print(f"🌐 View analytics: https://crespo.world/crespomize.html")
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
