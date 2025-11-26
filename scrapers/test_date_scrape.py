#!/usr/bin/env python3
"""
Test script to debug date extraction from Instagram posts.
Uses arrow keys to navigate through 10 posts and outputs date extraction results.
"""

import sys
import os
import time
import random

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

# Cookies for testing
TEST_COOKIES = [
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


def setup_driver(browser='chrome'):
    """Set up browser driver"""
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
    
    return driver


def load_cookies(driver):
    """Load Instagram cookies"""
    print("  🌐 Loading Instagram...")
    driver.get("https://www.instagram.com")
    time.sleep(3)
    
    print("  🍪 Loading cookies...")
    try:
        for cookie in TEST_COOKIES:
            driver.add_cookie(cookie)
        driver.refresh()
        time.sleep(3)
        print("  ✅ Cookies loaded!")
        return True
    except Exception as e:
        print(f"  ❌ Error loading cookies: {e}")
        return False


def dismiss_modal(driver):
    """Try to dismiss any Instagram modals"""
    close_selectors = [
        "//button[@aria-label='Close']",
        "//div[@role='button' and @aria-label='Close']",
        "//*[name()='svg' and @aria-label='Close']/..",
        "//button[contains(text(), 'Not Now')]",
        "//button[contains(text(), 'Not now')]",
    ]
    
    for selector in close_selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for elem in elements:
                if elem.is_displayed():
                    elem.click()
                    time.sleep(1)
                    return True
        except:
            continue
    
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
    except:
        pass
    
    return False


def extract_date(driver):
    """
    Extract date from currently displayed post.
    Returns all available information for debugging.
    """
    result = {
        'url': driver.current_url,
        'reel_id': None,
        'date': None,
        'date_display': None,
        'method_used': None,
        'all_time_elements': [],
        'likes': None
    }
    
    # Get reel ID from URL
    current_url = driver.current_url
    if '/reel/' in current_url:
        result['reel_id'] = current_url.split('/reel/')[-1].rstrip('/').split('?')[0]
    elif '/p/' in current_url:
        result['reel_id'] = 'POST:' + current_url.split('/p/')[-1].rstrip('/').split('?')[0]
    
    # Find ALL time elements first for debugging
    try:
        all_times = driver.find_elements(By.TAG_NAME, "time")
        for i, t in enumerate(all_times):
            elem_info = {
                'index': i,
                'text': t.text,
                'datetime': t.get_attribute('datetime'),
                'class': t.get_attribute('class'),
                'title': t.get_attribute('title')
            }
            result['all_time_elements'].append(elem_info)
    except Exception as e:
        result['all_time_elements'] = [f"ERROR: {e}"]
    
    # Method 1: CSS selector for specific class
    try:
        time_elements = driver.find_elements(By.CSS_SELECTOR, "time.x1p4m5qa")
        if time_elements:
            elem = time_elements[0]
            result['date'] = elem.get_attribute('datetime')
            result['date_display'] = elem.text
            result['method_used'] = 'CSS: time.x1p4m5qa'
    except Exception as e:
        pass
    
    # Method 2: If no date found, try any time element with datetime and title
    if not result['date']:
        try:
            all_times = driver.find_elements(By.TAG_NAME, "time")
            for t in all_times:
                datetime_val = t.get_attribute('datetime')
                title_val = t.get_attribute('title')
                # The post date usually has both datetime and title attributes
                if datetime_val and title_val:
                    result['date'] = datetime_val
                    result['date_display'] = t.text
                    result['method_used'] = 'Fallback: time with datetime+title'
                    break
        except:
            pass
    
    # Method 3: If still no date, try first time element with datetime
    if not result['date']:
        try:
            all_times = driver.find_elements(By.TAG_NAME, "time")
            for t in all_times:
                datetime_val = t.get_attribute('datetime')
                if datetime_val:
                    result['date'] = datetime_val
                    result['date_display'] = t.text
                    result['method_used'] = 'Fallback: first time with datetime'
                    break
        except:
            pass
    
    # Extract likes
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        import re
        others_match = re.search(r'and\s+([\d,.]+[KMB]?)\s+others', body_text, re.IGNORECASE)
        if others_match:
            result['likes'] = others_match.group(1)
        else:
            like_match = re.search(r'([\d,.]+[KMB]?)\s+likes?', body_text, re.IGNORECASE)
            if like_match:
                result['likes'] = like_match.group(1)
    except:
        pass
    
    return result


def run_test(username="popdartsgame"):
    """Run the test on a specified account"""
    print("\n" + "="*70)
    print("🧪 DATE EXTRACTION TEST (Arrow Navigation)")
    print("="*70)
    
    # Select browser
    print("\nSelect browser:")
    print("1. Chrome (Recommended)")
    print("2. Firefox")
    choice = input("Enter choice (1 or 2, default=Chrome): ").strip()
    browser = 'firefox' if choice == '2' else 'chrome'
    
    # Get username
    user_input = input(f"\nEnter Instagram username to test [{username}]: ").strip()
    if user_input:
        username = user_input
    
    print(f"\n�� Testing date extraction for @{username}")
    
    # Set up driver
    driver = setup_driver(browser)
    
    try:
        # Load cookies
        if not load_cookies(driver):
            print("❌ Failed to load cookies")
            return
        
        # Dismiss any modals
        dismiss_modal(driver)
        time.sleep(2)
        
        # Go to the reels page
        reels_url = f"https://www.instagram.com/{username}/reels/"
        print(f"\n  📄 Navigating to {reels_url}")
        driver.get(reels_url)
        time.sleep(4)
        
        # Dismiss any modals again
        dismiss_modal(driver)
        
        # Find and click first reel
        print("  🔍 Looking for first reel...")
        post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
        
        if not post_links:
            print("  ⚠️ No reels found, trying main profile...")
            driver.get(f"https://www.instagram.com/{username}/")
            time.sleep(3)
            dismiss_modal(driver)
            post_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/p/')]")
        
        if not post_links:
            print("  ❌ No posts found!")
            return
        
        print(f"  ✅ Found {len(post_links)} posts")
        print("  🖱️ Clicking first post...")
        
        try:
            post_links[0].click()
        except:
            driver.execute_script("arguments[0].click();", post_links[0])
        
        time.sleep(3)
        
        # Now navigate through 10 posts using arrow keys
        num_posts = 10
        results = []
        
        print(f"\n  ➡️ Extracting dates from {num_posts} posts using arrow navigation...\n")
        
        body = driver.find_element(By.TAG_NAME, "body")
        
        for post_num in range(num_posts):
            # Wait a bit for content to load
            time.sleep(1.5)
            
            # Extract date
            result = extract_date(driver)
            results.append(result)
            
            # Print result
            date_str = result['date_display'] if result['date_display'] else 'NOT FOUND'
            datetime_str = result['date'] if result['date'] else 'N/A'
            method_str = result['method_used'] if result['method_used'] else 'NONE'
            likes_str = result['likes'] if result['likes'] else 'N/A'
            
            print(f"  [{post_num+1:2}] {result['reel_id'] or 'Unknown'}")
            print(f"       Date: {date_str}")
            print(f"       Datetime: {datetime_str}")
            print(f"       Method: {method_str}")
            print(f"       Likes: {likes_str}")
            print(f"       Time elements found: {len(result['all_time_elements'])}")
            if result['all_time_elements'] and not result['date']:
                # Show what time elements we found if date extraction failed
                print(f"       Available time elements:")
                for elem in result['all_time_elements'][:3]:
                    if isinstance(elem, dict):
                        print(f"         [{elem['index']}] class='{elem['class']}' text='{elem['text']}' datetime='{elem['datetime']}'")
            print()
            
            # Navigate to next post
            if post_num < num_posts - 1:
                body.send_keys(Keys.ARROW_RIGHT)
        
        # Summary
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print("="*70)
        dates_found = sum(1 for r in results if r['date'])
        print(f"  Dates found: {dates_found}/{num_posts}")
        print(f"  Methods used:")
        methods = {}
        for r in results:
            m = r['method_used'] or 'NONE'
            methods[m] = methods.get(m, 0) + 1
        for m, count in methods.items():
            print(f"    {m}: {count}")
        
        # Keep browser open for inspection
        input("\nPress Enter to close browser...")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    run_test()
