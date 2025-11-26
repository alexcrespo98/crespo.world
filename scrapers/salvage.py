#!/usr/bin/env python3
"""
Instagram Salvage Script v2.0
- Opens existing Excel file and finds entries with missing dates
- URL scrapes to get missing date information
- Falls back to incognito mode if rate limited (429 error)
- Adds jitter to avoid rate limiting
- Saves updated data back to Excel
- Supports both Chrome and Firefox browsers
- Independent cookie management
"""

import sys
import subprocess
import os
from datetime import datetime
import time
import re
import random
import pandas as pd
from pathlib import Path

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

# Independent cookies for salvage.py (updated with latest Firefox session)
SALVAGE_COOKIES = [
    {'name': 'sessionid',  'value': '8438482535%3AMPEOwRDuMthipr%3A27%3AAYguJpa8sihvpLJqMSyswW-vqrU4gKsC-WHeCKl8gQ', 'domain': '.instagram.com'},
    {'name': 'csrftoken',  'value': 'PDZd_D2WZI-jbxK42IHbh7', 'domain': '.instagram.com'},
    {'name': 'ds_user_id', 'value': '8438482535', 'domain': '.instagram.com'},
    {'name': 'mid',        'value': 'aScXdwALAAHefecqIK7Kolvd0S83', 'domain': '.instagram.com'},
    {'name': 'ig_did',     'value': 'BDB1F779-BEE2-4C1B-BB51-B7BF706BFE25', 'domain': '.instagram.com'},
    {'name': 'datr',       'value': 'dxcnaSrRabzedk6Hc5PLcevi', 'domain': '.instagram.com'},
    {'name': 'rur',        'value': '"NHA\0548438482535\0541795705630:01fe1f0ed9e4a1adb09627c7fee409e812141bbd4b409a0c6f89f9c5bd22a7144d798e1b"', 'domain': '.instagram.com'},
    {'name': 'wd',         'value': '879x639', 'domain': '.instagram.com'},
    {'name': 'dpr',        'value': '1.5', 'domain': '.instagram.com'},
]

# Login credentials for Instagram
INSTAGRAM_USERNAME = "crespoworld"
INSTAGRAM_PASSWORD = "deleteme"


class InstagramSalvage:
    def __init__(self):
        self.driver = None
        self.incognito_driver = None
        self.rate_limited = False
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.browser_choice = 'chrome'  # Default browser
        self.cookies = SALVAGE_COOKIES.copy()  # Use independent cookies
        self.incognito_failed = False  # Track if incognito already failed
        
    def install_package(self, package):
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

    def ensure_packages(self):
        packages_needed = []
        required = {
            'selenium': 'selenium',
            'webdriver_manager': 'webdriver-manager',
            'pandas': 'pandas',
            'openpyxl': 'openpyxl'
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

    def add_jitter(self, base_delay=1.0, max_jitter=2.0):
        """Add random jitter to delays to avoid rate limiting"""
        jitter = random.uniform(0, max_jitter)
        total_delay = base_delay + jitter
        time.sleep(total_delay)
        return total_delay

    def parse_firefox_cookies(self, cookie_text):
        """
        Parse Firefox/Netscape cookie format into Selenium cookie format.
        """
        cookies = []
        lines = cookie_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                if line.startswith('#HttpOnly_'):
                    line = line.replace('#HttpOnly_', '')
                else:
                    continue
            
            parts = line.split('\t')
            if len(parts) >= 7:
                domain = parts[0]
                name = parts[5]
                value = parts[6]
                
                if 'instagram.com' in domain:
                    cookie = {
                        'name': name,
                        'value': value,
                        'domain': '.instagram.com'
                    }
                    cookies.append(cookie)
        
        return cookies

    def prompt_for_new_cookies(self):
        """
        Prompt user to paste new Firefox cookies when authentication fails.
        """
        print("\n" + "="*70)
        print("🍪 COOKIE UPDATE REQUIRED")
        print("="*70)
        print("\nYour session cookies may have expired. Please provide new cookies.")
        print("\nTo get cookies from Firefox:")
        print("  1. Install 'Cookie-Editor' browser extension")
        print("  2. Go to instagram.com and make sure you're logged in")
        print("  3. Click Cookie-Editor icon → Export → Netscape format")
        print("  4. Paste the cookies below")
        print()
        
        choice = input("Would you like to paste new cookies? (y/n): ").strip().lower()
        if choice != 'y':
            return None
        
        print("\nPaste your Firefox cookies below.")
        print("When done, press Enter twice (empty line) to finish:\n")
        
        lines = []
        empty_line_count = 0
        
        while True:
            try:
                line = input()
                if line == '':
                    empty_line_count += 1
                    if empty_line_count >= 1:
                        break
                else:
                    empty_line_count = 0
                    lines.append(line)
            except EOFError:
                break
        
        if not lines:
            print("❌ No cookies provided")
            return None
        
        cookie_text = '\n'.join(lines)
        cookies = self.parse_firefox_cookies(cookie_text)
        
        if not cookies:
            print("❌ Could not parse any valid Instagram cookies")
            return None
        
        print(f"\n✅ Parsed {len(cookies)} Instagram cookies")
        return cookies

    def select_browser(self):
        """Let user select browser (Chrome or Firefox)"""
        print("\n" + "="*70)
        print("🌐 SELECT BROWSER")
        print("="*70)
        print("\n1. Chrome (Recommended)")
        print("2. Firefox")
        print()
        while True:
            choice = input("Enter your choice (1 or 2, default=Chrome): ").strip()
            if choice == '1' or choice == '':
                self.browser_choice = 'chrome'
                return 'chrome'
            elif choice == '2':
                self.browser_choice = 'firefox'
                return 'firefox'
            else:
                print("Invalid choice. Please enter 1 or 2.")

    def setup_driver(self, incognito=False):
        """Set up browser driver, optionally in incognito mode"""
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.firefox import GeckoDriverManager
        
        mode_str = "incognito/private" if incognito else "normal"
        browser_name = self.browser_choice.capitalize()
        print(f"  🌐 Setting up {browser_name} driver ({mode_str} mode)...")
        
        if self.browser_choice == 'chrome':
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--disable-logging")
            
            if incognito:
                chrome_options.add_argument("--incognito")
            
            service = ChromeService(ChromeDriverManager().install())
            service.log_path = os.devnull
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Firefox
            firefox_options = FirefoxOptions()
            firefox_options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0")
            
            if incognito:
                firefox_options.add_argument("-private")
            
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=firefox_options)
            driver.maximize_window()
        
        print("  🌐 Loading Instagram...")
        driver.get("https://www.instagram.com")
        self.add_jitter(3, 1)
        
        logged_in = False
        
        if not incognito and self.cookies:
            print("  🍪 Loading cookies...")
            try:
                for cookie in self.cookies:
                    driver.add_cookie(cookie)
                driver.refresh()
                self.add_jitter(3, 1)
                print("  ✅ Cookies loaded!")
                
                # Check if actually logged in
                self.dismiss_modal(driver)
                profile_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/direct/') or contains(@href, '/accounts/')]")
                if profile_links:
                    logged_in = True
                    print("  ✅ Already logged in via cookies!")
            except Exception as e:
                print(f"  ⚠️ Could not load cookies: {e}")
        
        # If not logged in, try credentials
        if not logged_in and not incognito:
            print("  ⚠️ Cookies didn't work, attempting login with credentials...")
            if self.login_to_instagram(driver):
                logged_in = True
        
        # If still not logged in, offer to paste new cookies
        if not logged_in and not incognito:
            print("  ❌ Login failed!")
            print("\n  Would you like to:")
            print("    1. Provide new Firefox cookies")
            print("    2. Continue anyway (limited data)")
            print("    3. Exit")
            
            choice = input("\n  Enter choice (1/2/3): ").strip()
            
            if choice == '1':
                new_cookies = self.prompt_for_new_cookies()
                if new_cookies:
                    self.cookies = new_cookies
                    driver.delete_all_cookies()
                    for cookie in new_cookies:
                        try:
                            driver.add_cookie(cookie)
                        except:
                            pass
                    driver.refresh()
                    self.add_jitter(3, 1)
                    self.dismiss_modal(driver)
                    print("  ✅ New cookies applied!")
            elif choice == '3':
                print("\n  Exiting...")
                driver.quit()
                sys.exit(0)
        
        # For incognito, try to log in
        if incognito:
            if not self.login_to_instagram(driver):
                print("  ❌ Incognito login failed!")
                self.incognito_failed = True
        
        return driver

    def login_to_instagram(self, driver):
        """Log in to Instagram using credentials"""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        print("  🔐 Attempting to log in...")
        
        try:
            driver.get("https://www.instagram.com/accounts/login/")
            self.add_jitter(3, 1)
            
            # Accept cookies if prompted
            try:
                cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Allow') or contains(text(), 'Accept')]")
                for btn in cookie_buttons:
                    if btn.is_displayed():
                        btn.click()
                        self.add_jitter(1, 0.5)
                        break
            except:
                pass
            
            # Find and fill username
            try:
                username_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                username_field.clear()
                username_field.send_keys(INSTAGRAM_USERNAME)
                self.add_jitter(0.5, 0.3)
            except Exception as e:
                print(f"  ❌ Could not find username field: {e}")
                return False
            
            # Find and fill password
            try:
                password_field = driver.find_element(By.NAME, "password")
                password_field.clear()
                password_field.send_keys(INSTAGRAM_PASSWORD)
                self.add_jitter(0.5, 0.3)
            except Exception as e:
                print(f"  ❌ Could not find password field: {e}")
                return False
            
            # Click login button
            try:
                login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                print("  ⏳ Waiting for login...")
                self.add_jitter(5, 2)
            except Exception as e:
                print(f"  ❌ Could not find login button: {e}")
                return False
            
            # Check if login was successful
            if "/accounts/login" in driver.current_url:
                print("  ❌ Login failed - still on login page")
                return False
            
            # Dismiss any popups
            self.dismiss_modal(driver)
            
            print("  ✅ Login successful!")
            return True
            
        except Exception as e:
            print(f"  ❌ Login error: {e}")
            return False

    def dismiss_modal(self, driver, max_attempts=3):
        """Dismiss Instagram login/signup modal"""
        from selenium.webdriver.common.keys import Keys
        
        for attempt in range(max_attempts):
            try:
                close_selectors = [
                    "//button[@aria-label='Close']",
                    "//div[@role='button' and @aria-label='Close']",
                    "//button[contains(text(), 'Not Now')]",
                    "//button[contains(text(), 'Not now')]",
                ]
                
                for selector in close_selectors:
                    try:
                        close_btn = driver.find_element(By.XPATH, selector)
                        if close_btn.is_displayed():
                            close_btn.click()
                            self.add_jitter(1, 0.5)
                            return True
                    except:
                        continue
                
                # Try pressing Escape
                try:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    self.add_jitter(1, 0.5)
                    return True
                except:
                    pass
                    
            except:
                pass
        
        return False

    def check_for_rate_limit(self, driver):
        """Check if we've hit a 429 rate limit"""
        try:
            page_source = driver.page_source.lower()
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            rate_limit_indicators = [
                "rate limit",
                "too many requests",
                "please wait",
                "try again later",
                "something went wrong"
            ]
            
            for indicator in rate_limit_indicators:
                if indicator in page_source or indicator in body_text:
                    return True
            
            # Check for 429 in network (if visible in page)
            if "429" in page_source:
                return True
                
        except:
            pass
        
        return False

    def parse_date_to_timestamp(self, date_str):
        """Parse ISO date string to datetime"""
        if not date_str:
            return None
        try:
            if 'T' in str(date_str):
                date_str = str(date_str).replace('Z', '').split('.')[0]
                return datetime.fromisoformat(date_str)
        except:
            pass
        return None

    def scrape_single_url(self, driver, reel_id):
        """Scrape a single reel URL for date information"""
        reel_url = f"https://www.instagram.com/reel/{reel_id}/"
        
        try:
            driver.get(reel_url)
            self.add_jitter(2, 1.5)  # Jitter to avoid rate limiting
            
            # Check for rate limiting
            if self.check_for_rate_limit(driver):
                return None, True  # Return None data, True for rate limited
            
            data = {
                'date': None,
                'date_display': None,
            }
            
            # Extract date
            try:
                time_elements = driver.find_elements(By.TAG_NAME, "time")
                if time_elements:
                    time_elem = time_elements[0]
                    data['date'] = time_elem.get_attribute('datetime')
                    data['date_display'] = time_elem.text
            except:
                pass
            
            return data, False  # Return data, not rate limited
            
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            return None, False

    def arrow_scrape_dates(self, driver, username, reel_ids):
        """
        Arrow scrape method - click first reel and use arrow keys to navigate.
        More reliable than visiting individual URLs (avoids 429 rate limits).
        
        Args:
            driver: Selenium driver
            username: Instagram username  
            reel_ids: List of reel IDs to find dates for
            
        Returns:
            dict: {reel_id: {'date': ..., 'date_display': ...}}
        """
        from selenium.webdriver.common.keys import Keys
        
        print(f"\n  ➡️ Arrow scrape for {len(reel_ids)} missing dates...")
        
        reel_ids_needed = set(reel_ids)
        arrow_data = {}  # reel_id -> date data
        
        # Try /reels/ page first, then main profile as fallback
        pages_to_try = [
            f"https://www.instagram.com/{username}/reels/",
            f"https://www.instagram.com/{username}/"
        ]
        
        for page_url in pages_to_try:
            if len(arrow_data) >= len(reel_ids_needed):
                break
            
            page_type = "reels" if "/reels/" in page_url else "main"
            print(f"    📄 Trying {page_type} page...")
            
            try:
                driver.get(page_url)
                self.add_jitter(3, 1)
                
                # Dismiss any modals
                self.dismiss_modal(driver)
                
                # Find first clickable post/reel
                post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/p/')]")
                
                if not post_links:
                    print(f"    ⚠️ No posts found on {page_type} page")
                    continue
                
                # Click the first post
                first_post = post_links[0]
                print(f"    🖱️ Clicking first post...")
                
                try:
                    first_post.click()
                except:
                    driver.execute_script("arguments[0].click();", first_post)
                
                self.add_jitter(2, 1)
                
                # Navigate through posts using arrow keys
                body = driver.find_element(By.TAG_NAME, "body")
                posts_processed = 0
                consecutive_misses = 0
                max_consecutive_misses = 15
                max_posts = len(reel_ids) + 100
                
                while posts_processed < max_posts and consecutive_misses < max_consecutive_misses:
                    current_url = driver.current_url
                    current_reel_id = None
                    
                    if '/reel/' in current_url:
                        current_reel_id = current_url.split('/reel/')[-1].rstrip('/').split('?')[0]
                    elif '/p/' in current_url:
                        # Regular post, skip
                        body.send_keys(Keys.ARROW_RIGHT)
                        self.add_jitter(0.5, 0.3)
                        posts_processed += 1
                        continue
                    
                    if current_reel_id and current_reel_id in reel_ids_needed and current_reel_id not in arrow_data:
                        # Extract date
                        date_info = self.extract_date_from_view(driver)
                        
                        if date_info.get('date'):
                            arrow_data[current_reel_id] = date_info
                            consecutive_misses = 0
                            print(f"    [{len(arrow_data)}/{len(reel_ids_needed)}] {current_reel_id}: {date_info.get('date_display', 'N/A')}")
                        else:
                            consecutive_misses += 1
                    else:
                        consecutive_misses += 1
                    
                    body.send_keys(Keys.ARROW_RIGHT)
                    self.add_jitter(0.8, 0.5)
                    posts_processed += 1
                    
                    if len(arrow_data) >= len(reel_ids_needed):
                        print(f"    ✅ Found all {len(arrow_data)} dates!")
                        break
                
                # Close modal
                body.send_keys(Keys.ESCAPE)
                self.add_jitter(1, 0.5)
                
                print(f"    📊 Found {len(arrow_data)} dates from {page_type} page")
                
            except Exception as e:
                print(f"    ❌ Error on {page_type} page: {str(e)}")
                continue
        
        return arrow_data

    def extract_date_from_view(self, driver):
        """Extract date from currently displayed reel using multiple methods"""
        data = {'date': None, 'date_display': None}
        
        # Method 1: CSS selector for specific class (most reliable)
        try:
            time_elements = driver.find_elements(By.CSS_SELECTOR, "time.x1p4m5qa")
            if time_elements:
                time_elem = time_elements[0]
                data['date'] = time_elem.get_attribute('datetime')
                data['date_display'] = time_elem.text
                return data
        except:
            pass
        
        # Method 2: Look for time element with both datetime and title attributes
        # The post date usually has both, while comment dates may only have datetime
        if not data['date']:
            try:
                time_elements = driver.find_elements(By.TAG_NAME, "time")
                for time_elem in time_elements:
                    datetime_attr = time_elem.get_attribute('datetime')
                    title_attr = time_elem.get_attribute('title')
                    if datetime_attr and title_attr:
                        data['date'] = datetime_attr
                        data['date_display'] = time_elem.text
                        return data
            except:
                pass
        
        # Method 3: Fallback to first time element with datetime
        if not data['date']:
            try:
                time_elements = driver.find_elements(By.TAG_NAME, "time")
                for time_elem in time_elements:
                    datetime_attr = time_elem.get_attribute('datetime')
                    if datetime_attr:
                        data['date'] = datetime_attr
                        data['date_display'] = time_elem.text
                        return data
            except:
                pass
        
        return data

    def switch_to_incognito(self):
        """Switch to incognito mode when rate limited"""
        print("\n  🔄 Switching to incognito mode...")
        
        # Close current driver if exists
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        # If incognito already failed, prompt for new cookies instead
        if self.incognito_failed:
            print("\n  ⚠️ Incognito mode already failed. Need new cookies.")
            return self.prompt_for_cookies_and_restart()
        
        # Set up incognito driver
        self.incognito_driver = self.setup_driver(incognito=True)
        self.rate_limited = False
        self.consecutive_failures = 0
        
        # Check if incognito setup failed
        if self.incognito_failed:
            print("\n  ❌ Incognito login failed!")
            return self.prompt_for_cookies_and_restart()
        
        print("  ✅ Incognito mode active!")
        return self.incognito_driver

    def prompt_for_cookies_and_restart(self):
        """Prompt for new cookies when incognito fails"""
        print("\n" + "="*70)
        print("🍪 NEW COOKIES REQUIRED")
        print("="*70)
        print("\nBoth normal and incognito modes have failed.")
        print("Please provide fresh cookies from your browser.\n")
        
        new_cookies = self.prompt_for_new_cookies()
        
        if not new_cookies:
            print("\n❌ No cookies provided. Cannot continue.")
            print("Would you like to:")
            print("  1. Try again with new cookies")
            print("  2. Exit")
            
            choice = input("\nEnter choice (1/2): ").strip()
            if choice == '1':
                return self.prompt_for_cookies_and_restart()
            else:
                sys.exit(1)
        
        # Update cookies and set up new driver
        self.cookies = new_cookies
        self.incognito_failed = False  # Reset flag
        self.consecutive_failures = 0
        
        print("\n🌐 Setting up browser with new cookies...")
        self.driver = self.setup_driver(incognito=False)
        return self.driver

    def find_missing_dates(self, excel_path):
        """Find all entries with missing dates in the Excel file"""
        print(f"\n📂 Loading Excel file: {excel_path}")
        
        try:
            excel_data = pd.read_excel(excel_path, sheet_name=None, index_col=0)
        except Exception as e:
            print(f"❌ Could not load Excel file: {e}")
            return None, None
        
        missing_dates = {}
        
        for sheet_name, df in excel_data.items():
            print(f"\n  📊 Checking sheet: {sheet_name}")
            
            # Find reel_*_date rows
            date_rows = [idx for idx in df.index if str(idx).startswith('reel_') and str(idx).endswith('_date')]
            
            sheet_missing = []
            for row in date_rows:
                # Check the latest column for missing dates
                if df.shape[1] > 0:
                    latest_col = df.columns[-1]
                    value = df.loc[row, latest_col]
                    
                    # Check if date is missing or empty
                    if pd.isna(value) or value == '' or value is None:
                        # Extract reel_id from row name (reel_XXXXX_date -> XXXXX)
                        reel_id = row.replace('reel_', '').replace('_date', '')
                        sheet_missing.append(reel_id)
            
            if sheet_missing:
                missing_dates[sheet_name] = sheet_missing
                print(f"    Found {len(sheet_missing)} entries with missing dates")
            else:
                print(f"    ✅ No missing dates")
        
        total_missing = sum(len(v) for v in missing_dates.values())
        print(f"\n📊 Total entries with missing dates: {total_missing}")
        
        return excel_data, missing_dates

    def salvage_dates(self, excel_path):
        """Main function to salvage missing dates using arrow scrape method"""
        self.ensure_packages()
        
        print("\n" + "="*70)
        print("🔧 Instagram Date Salvage Tool v2.0")
        print("="*70)
        
        # Find missing dates
        excel_data, missing_dates = self.find_missing_dates(excel_path)
        
        if not missing_dates:
            print("\n✅ No missing dates to salvage!")
            return
        
        total_missing = sum(len(v) for v in missing_dates.values())
        
        confirm = input(f"\n🔄 Salvage {total_missing} missing dates? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Cancelled")
            return
        
        # Select browser
        self.select_browser()
        
        # Set up driver
        print("\n🌐 Setting up browser...")
        self.driver = self.setup_driver(incognito=False)
        current_driver = self.driver
        
        salvaged_count = 0
        failed_count = 0
        
        try:
            for sheet_name, reel_ids in missing_dates.items():
                print(f"\n📊 Processing sheet: {sheet_name} ({len(reel_ids)} missing dates)")
                df = excel_data[sheet_name]
                latest_col = df.columns[-1]
                
                # Use arrow scrape first (more reliable, avoids rate limits)
                print(f"\n  🎯 Using arrow scrape method for {sheet_name}...")
                arrow_results = self.arrow_scrape_dates(current_driver, sheet_name, reel_ids)
                
                # Apply arrow scrape results
                arrow_found = 0
                remaining_ids = []
                
                for reel_id in reel_ids:
                    if reel_id in arrow_results and arrow_results[reel_id].get('date'):
                        date_row = f"reel_{reel_id}_date"
                        date_display_row = f"reel_{reel_id}_date_display"
                        
                        df.loc[date_row, latest_col] = arrow_results[reel_id]['date']
                        if date_display_row in df.index:
                            df.loc[date_display_row, latest_col] = arrow_results[reel_id]['date_display']
                        
                        salvaged_count += 1
                        arrow_found += 1
                    else:
                        remaining_ids.append(reel_id)
                
                print(f"  ✅ Arrow scrape found {arrow_found}/{len(reel_ids)} dates")
                
                # Fall back to individual URL scrape for remaining IDs
                if remaining_ids:
                    print(f"\n  🔄 Falling back to individual URL scrape for {len(remaining_ids)} remaining...")
                    
                    for idx, reel_id in enumerate(remaining_ids):
                        print(f"    [{idx+1}/{len(remaining_ids)}] Scraping {reel_id}...", end=" ")
                        
                        data, rate_limited = self.scrape_single_url(current_driver, reel_id)
                        
                        # Handle rate limiting
                        if rate_limited:
                            print("⚠️ Rate limited!")
                            self.consecutive_failures += 1
                            
                            if self.consecutive_failures >= self.max_consecutive_failures:
                                print("\n    🔄 Too many failures, switching to incognito...")
                                current_driver = self.switch_to_incognito()
                                
                                if current_driver is None:
                                    print("    ❌ Could not recover, skipping remaining...")
                                    failed_count += len(remaining_ids) - idx
                                    break
                                
                                self.consecutive_failures = 0
                                
                                # Retry with incognito
                                data, rate_limited = self.scrape_single_url(current_driver, reel_id)
                        
                        if data and data.get('date'):
                            date_row = f"reel_{reel_id}_date"
                            date_display_row = f"reel_{reel_id}_date_display"
                            
                            df.loc[date_row, latest_col] = data['date']
                            if date_display_row in df.index:
                                df.loc[date_display_row, latest_col] = data['date_display']
                            
                            print(f"✅ {data.get('date_display', 'N/A')}")
                            salvaged_count += 1
                            self.consecutive_failures = 0
                        else:
                            print("❌ Failed")
                            failed_count += 1
                            self.consecutive_failures += 1
                        
                        # Add jitter between requests
                        self.add_jitter(1.5, 2.0)
                
                # Update the excel_data with modified df
                excel_data[sheet_name] = df
            
            # Save updated Excel
            print(f"\n💾 Saving updated Excel file...")
            output_path = excel_path.replace('.xlsx', '_salvaged.xlsx')
            
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for sheet_name, df in excel_data.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31])
            
            print(f"\n" + "="*70)
            print("✅ SALVAGE COMPLETE!")
            print("="*70)
            print(f"  📊 Salvaged: {salvaged_count} dates")
            print(f"  ❌ Failed: {failed_count}")
            print(f"  📁 Saved to: {output_path}")
            
        finally:
            # Clean up drivers
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            if self.incognito_driver:
                try:
                    self.incognito_driver.quit()
                except:
                    pass


def main():
    salvage = InstagramSalvage()
    
    # Get Excel file path
    print("\n🔧 Instagram Date Salvage Tool")
    print("="*50)
    
    # Check for command line argument
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        # Default path or ask user
        default_path = "instagram_reels_analytics_tracker.xlsx"
        excel_path = input(f"\nEnter Excel file path [{default_path}]: ").strip()
        if not excel_path:
            excel_path = default_path
    
    if not os.path.exists(excel_path):
        print(f"❌ File not found: {excel_path}")
        sys.exit(1)
    
    salvage.salvage_dates(excel_path)


if __name__ == "__main__":
    main()
