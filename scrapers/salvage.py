#!/usr/bin/env python3
"""
Instagram Salvage Script v1.0
- Opens existing Excel file and finds entries with missing dates
- URL scrapes to get missing date information
- Falls back to incognito mode if rate limited (429 error)
- Adds jitter to avoid rate limiting
- Saves updated data back to Excel
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
from selenium.webdriver.chrome.service import Service as ChromeService

# Import cookies and credentials from main scraper
try:
    from insta_scraper import INSTAGRAM_COOKIES, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD
except ImportError:
    print("⚠️ Could not import from insta_scraper.py, using defaults")
    INSTAGRAM_COOKIES = []
    INSTAGRAM_USERNAME = "crespoworld"
    INSTAGRAM_PASSWORD = "deleteme"


class InstagramSalvage:
    def __init__(self):
        self.driver = None
        self.incognito_driver = None
        self.rate_limited = False
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
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

    def setup_driver(self, incognito=False):
        """Set up Chrome driver, optionally in incognito mode"""
        from webdriver_manager.chrome import ChromeDriverManager
        global INSTAGRAM_COOKIES
        
        mode_str = "incognito" if incognito else "normal"
        print(f"  🌐 Setting up Chrome driver ({mode_str} mode)...")
        
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
        
        print("  🌐 Loading Instagram...")
        driver.get("https://www.instagram.com")
        self.add_jitter(3, 1)
        
        logged_in = False
        
        if not incognito and INSTAGRAM_COOKIES:
            print("  🍪 Loading cookies...")
            try:
                for cookie in INSTAGRAM_COOKIES:
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
                    INSTAGRAM_COOKIES = new_cookies
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
        
        # For incognito, always try to log in
        if incognito:
            self.login_to_instagram(driver)
        
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

    def switch_to_incognito(self):
        """Switch to incognito mode when rate limited"""
        print("\n  🔄 Switching to incognito mode...")
        
        # Close current driver if exists
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        # Set up incognito driver
        self.incognito_driver = self.setup_driver(incognito=True)
        self.rate_limited = False
        self.consecutive_failures = 0
        
        print("  ✅ Incognito mode active!")
        return self.incognito_driver

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
        """Main function to salvage missing dates"""
        self.ensure_packages()
        
        print("\n" + "="*70)
        print("🔧 Instagram Date Salvage Tool v1.0")
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
        
        # Set up driver
        print("\n🌐 Setting up browser...")
        self.driver = self.setup_driver(incognito=False)
        current_driver = self.driver
        
        salvaged_count = 0
        failed_count = 0
        
        try:
            for sheet_name, reel_ids in missing_dates.items():
                print(f"\n📊 Processing sheet: {sheet_name}")
                df = excel_data[sheet_name]
                latest_col = df.columns[-1]
                
                for idx, reel_id in enumerate(reel_ids):
                    print(f"  [{idx+1}/{len(reel_ids)}] Scraping {reel_id}...", end=" ")
                    
                    data, rate_limited = self.scrape_single_url(current_driver, reel_id)
                    
                    # Handle rate limiting
                    if rate_limited:
                        print("⚠️ Rate limited!")
                        self.consecutive_failures += 1
                        
                        if self.consecutive_failures >= self.max_consecutive_failures:
                            print("\n  🔄 Too many failures, switching to incognito...")
                            current_driver = self.switch_to_incognito()
                            self.consecutive_failures = 0
                            
                            # Retry with incognito
                            data, rate_limited = self.scrape_single_url(current_driver, reel_id)
                    
                    if data and data.get('date'):
                        # Update the dataframe
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
                    
                    # Add extra jitter between requests
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
