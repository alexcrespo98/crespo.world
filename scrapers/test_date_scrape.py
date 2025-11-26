#!/usr/bin/env python3
"""
Test script to debug date extraction from Instagram posts.
Opens a reel and prints ALL text content found on the page
to help identify where date information is located.
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

# Cookies for testing (same as salvage.py)
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
    
    # Try Escape key
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
    except:
        pass
    
    return False


def extract_all_text_content(driver):
    """
    Extract ALL text content from the page in various ways
    to help identify where date information is located.
    """
    results = {}
    
    # 1. Get full body text
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        results['body_text'] = body.text
    except Exception as e:
        results['body_text'] = f"ERROR: {e}"
    
    # 2. Look for <time> elements (standard HTML date elements)
    try:
        time_elements = driver.find_elements(By.TAG_NAME, "time")
        results['time_elements'] = []
        for i, elem in enumerate(time_elements):
            results['time_elements'].append({
                'index': i,
                'text': elem.text,
                'datetime': elem.get_attribute('datetime'),
                'title': elem.get_attribute('title'),
                'outerHTML': elem.get_attribute('outerHTML')[:500] if elem.get_attribute('outerHTML') else None
            })
    except Exception as e:
        results['time_elements'] = f"ERROR: {e}"
    
    # 3. Look for elements with "ago" text (like "3 weeks ago")
    try:
        ago_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'ago')]")
        results['ago_elements'] = []
        for i, elem in enumerate(ago_elements[:10]):  # Limit to first 10
            results['ago_elements'].append({
                'index': i,
                'text': elem.text[:200] if elem.text else None,
                'tag': elem.tag_name,
                'outerHTML': elem.get_attribute('outerHTML')[:300] if elem.get_attribute('outerHTML') else None
            })
    except Exception as e:
        results['ago_elements'] = f"ERROR: {e}"
    
    # 4. Look for elements with month names
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    try:
        results['month_elements'] = []
        for month in months:
            month_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{month}')]")
            for elem in month_elements[:3]:  # Limit to first 3 per month
                results['month_elements'].append({
                    'month': month,
                    'text': elem.text[:200] if elem.text else None,
                    'tag': elem.tag_name,
                })
    except Exception as e:
        results['month_elements'] = f"ERROR: {e}"
    
    # 5. Look for spans (often contain dates)
    try:
        spans = driver.find_elements(By.TAG_NAME, "span")
        results['span_samples'] = []
        for i, span in enumerate(spans):
            text = span.text.strip() if span.text else ""
            # Only include spans with text that might be date-related
            if text and len(text) < 50:
                lower_text = text.lower()
                if any(kw in lower_text for kw in ['ago', 'week', 'day', 'hour', 'minute', 'second', 
                                                     'january', 'february', 'march', 'april', 'may', 'june',
                                                     'july', 'august', 'september', 'october', 'november', 'december']):
                    results['span_samples'].append({
                        'index': i,
                        'text': text,
                    })
    except Exception as e:
        results['span_samples'] = f"ERROR: {e}"
    
    # 6. Current URL
    results['current_url'] = driver.current_url
    
    return results


def run_test(username="popdartsgame"):
    """Run the test on a specified account"""
    print("\n" + "="*70)
    print("🧪 DATE EXTRACTION TEST SCRIPT")
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
    
    print(f"\n📸 Testing date extraction for @{username}")
    
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
        
        # Now scrape the content from multiple posts
        output_lines = []
        num_posts = 5  # Test 5 posts
        
        for post_num in range(num_posts):
            output_lines.append("\n" + "="*70)
            output_lines.append(f"POST {post_num + 1}")
            output_lines.append("="*70)
            
            # Extract all text content
            results = extract_all_text_content(driver)
            
            output_lines.append(f"\n📍 URL: {results.get('current_url', 'N/A')}")
            
            # Time elements (most likely to have dates)
            output_lines.append("\n--- <time> ELEMENTS ---")
            if isinstance(results.get('time_elements'), list):
                for item in results['time_elements']:
                    output_lines.append(f"  [{item['index']}] text='{item['text']}' datetime='{item['datetime']}' title='{item['title']}'")
                    if item.get('outerHTML'):
                        output_lines.append(f"      HTML: {item['outerHTML']}")
            else:
                output_lines.append(f"  {results.get('time_elements')}")
            
            # Elements with "ago" 
            output_lines.append("\n--- ELEMENTS WITH 'ago' ---")
            if isinstance(results.get('ago_elements'), list):
                for item in results['ago_elements']:
                    output_lines.append(f"  [{item['index']}] <{item['tag']}> text='{item['text']}'")
            else:
                output_lines.append(f"  {results.get('ago_elements')}")
            
            # Elements with month names
            output_lines.append("\n--- ELEMENTS WITH MONTH NAMES ---")
            if isinstance(results.get('month_elements'), list):
                for item in results['month_elements']:
                    output_lines.append(f"  [{item['month']}] <{item['tag']}> text='{item['text']}'")
            else:
                output_lines.append(f"  {results.get('month_elements')}")
            
            # Span samples with date keywords
            output_lines.append("\n--- SPANS WITH DATE KEYWORDS ---")
            if isinstance(results.get('span_samples'), list):
                for item in results['span_samples']:
                    output_lines.append(f"  [{item['index']}] '{item['text']}'")
            else:
                output_lines.append(f"  {results.get('span_samples')}")
            
            # Full body text (truncated)
            output_lines.append("\n--- FULL BODY TEXT (first 2000 chars) ---")
            body_text = results.get('body_text', '')
            if body_text:
                output_lines.append(body_text[:2000])
            
            # Navigate to next post
            if post_num < num_posts - 1:
                print(f"  ➡️ Navigating to post {post_num + 2}...")
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(2)
        
        # Print all output
        full_output = "\n".join(output_lines)
        print(full_output)
        
        # Save to file
        output_file = f"date_scrape_test_{username}.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_output)
        
        print(f"\n✅ Output saved to: {output_file}")
        print("Please share the contents of this file so I can refine the date extraction!")
        
        # Keep browser open for inspection
        input("\nPress Enter to close browser...")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    run_test()
