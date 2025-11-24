#!/usr/bin/env python3
"""
Instagram Reels Analytics Tracker v2.9
- NEW: Arrow scrape FIRST to establish true order
- NEW: Hover scrape validates starting position and scrolls up if needed, then infinite scroll/scrapes
- NEW: Includes pinned posts in final data (marked as pinned)
- FIXED: Handles "liked by X and Y others" format
- FIXED: Uses reel_id as primary match for 100% accuracy
- Smart cross-reference between hover (reels) and arrow (main) data
- Auto-detects and skips photo posts that appear in main but not reels
- Hybrid method: arrow key navigation + hover scrape
- Updates Excel with separate tabs per account
- Auto-uploads to Google Drive
- Gets exact follower count via Instagram API
- MODIFIED: Deep scrape now goes back 2 years or to beginning of account
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

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

def ensure_packages():
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
            install_package(p)
        print("✅ All packages installed!")

def select_browser():
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

def get_exact_follower_count(username):
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

def parse_number(text):
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

def parse_date_to_timestamp(date_str):
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            date_str = date_str.replace('Z', '').split('.')[0]
            return datetime.fromisoformat(date_str)
    except:
        pass
    return None

def is_video_post(element):
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

def setup_driver(browser='chrome'):
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
        print("  🌐 Loading Instagram...")
        driver.get("https://www.instagram.com")
        time.sleep(3)
        print("  🍪 Loading cookies...")
        for cookie in INSTAGRAM_COOKIES:
            driver.add_cookie(cookie)
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

def extract_reel_data_from_overlay(driver):
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
                data['date_timestamp'] = parse_date_to_timestamp(data['date'])
        except:
            pass
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            others_match = re.search(r'and\s+([\d,.]+[KMB]?)\s+others', body_text, re.IGNORECASE)
            if others_match:
                data['likes'] = parse_number(others_match.group(1))
            else:
                like_match = re.search(r'([\d,.]+[KMB]?)\s+likes?', body_text, re.IGNORECASE)
                if like_match:
                    data['likes'] = parse_number(like_match.group(1))
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
                    data['comments'] = parse_number(comment_match.group(1))
                    break
        except:
            pass
    except:
        pass
    return data

def detect_pinned_posts(initial_reels):
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

def arrow_scrape_reels(driver, username, max_reels=100, deep_scrape=False, test_mode=False, use_main_profile=False):
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
            if is_video_post(link):
                first_video_link = link
                break
        if not first_video_link:
            print(f"  ⚠️  No videos found on main profile")
            return [], 0, False
        reel_links = [first_video_link]
    else:
        reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
    if not reel_links:
        return [], 0, False
    driver.execute_script("arguments[0].click();", reel_links[0])
    time.sleep(3)
    if test_mode:
        print(f"\n  🧪 STEP 1: Arrow scrape from {'MAIN PROFILE' if use_main_profile else '/reels/'} (establishing order)...")
    else:
        print(f"  📅 Step 1: Arrow key scraping (establishing order)...")
    consecutive_failures = 0
    FAILURE_THRESHOLD = 3
    initial_reels = []
    for idx in range(min(5, max_reels)):
        try:
            time.sleep(1)
            data = extract_reel_data_from_overlay(driver)
            if not data.get('reel_id'):
                consecutive_failures += 1
                if consecutive_failures >= FAILURE_THRESHOLD and not use_main_profile:
                    print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive failures detected - triggering fallback!")
                    return [], 0, True
                break
            if data.get('likes') is None and data.get('date') is None:
                consecutive_failures += 1
                if consecutive_failures >= FAILURE_THRESHOLD and not use_main_profile:
                    print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive N/A detected - triggering fallback!")
                    return [], 0, True
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
        return [], 0, False
    pinned_count = detect_pinned_posts(initial_reels)
    if test_mode and pinned_count > 0:
        print(f"    📌 Detected {pinned_count} pinned post(s) - will include in final data")
    for _ in range(len(initial_reels) - 1):
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_LEFT)
        time.sleep(0.8)
    arrow_data = []
    
    # Calculate cutoff date for deep scrape (2 years ago)
    cutoff_date = datetime.now() - timedelta(days=730)  # 2 years = 730 days
    
    # Use a large iteration count for deep scrape, but check dates
    max_iterations = 2000 if deep_scrape else max_reels  # Increased from 500
    consecutive_failures = 0
    consecutive_old_posts = 0  # Track posts older than cutoff
    
    for idx in range(max_iterations):
        try:
            time.sleep(1)
            data = extract_reel_data_from_overlay(driver)
            if not data.get('reel_id'):
                consecutive_failures += 1
                if consecutive_failures >= FAILURE_THRESHOLD and not use_main_profile:
                    print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive failures - triggering fallback!")
                    return arrow_data, pinned_count, True
                if test_mode:
                    print(f"    ⚠️  Arrow scrape stopped at {idx} - no more data")
                break
            if data.get('likes') is None and data.get('date') is None:
                consecutive_failures += 1
                if consecutive_failures >= FAILURE_THRESHOLD and not use_main_profile:
                    print(f"  ⚠️  {FAILURE_THRESHOLD} consecutive N/A - triggering fallback!")
                    return arrow_data, pinned_count, True
            else:
                consecutive_failures = 0
            
            # Check if we've gone back far enough for deep scrape
            if deep_scrape and data.get('date_timestamp'):
                if data['date_timestamp'] < cutoff_date:
                    consecutive_old_posts += 1
                    if consecutive_old_posts >= 5:  # Stop after 5 posts older than 2 years
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
                likes = data.get('likes', 'N/A')
                pinned_marker = " 📌PINNED" if data['is_pinned'] else ""
                print(f"    [{idx+1}] {reel_id}: {date}, {likes} likes{pinned_marker}")
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
    return arrow_data, pinned_count, False

def extract_views_from_container(container):
    try:
        text = container.text
        numbers = re.findall(r'\b([\d,.]+[KMB]?)\b', text)
        for num in numbers:
            parsed = parse_number(num)
            if parsed:
                return parsed
    except:
        pass
    return None

def extract_hover_overlay_data(parent):
    likes = None
    comments = None
    try:
        overlay_text = parent.text
        overlay_lines = [line.strip() for line in overlay_text.split('\n') if line.strip()]
        for line in overlay_lines:
            line_lower = line.lower()
            if 'and' in line_lower and 'others' in line_lower and not likes:
                match = re.search(r'and\s+([\d,.]+[KMB]?)\s+others', line_lower)
                if match:
                    likes = parse_number(match.group(1))
            if 'like' in line_lower and not likes:
                match = re.search(r'([\d,.]+[KMB]?)\s*like', line_lower)
                if match:
                    likes = parse_number(match.group(1))
            if 'comment' in line_lower and not comments:
                match = re.search(r'([\d,.]+[KMB]?)\s*comment', line_lower)
                if match:
                    comments = parse_number(match.group(1))
        if not likes or not comments:
            standalone_numbers = []
            for line in overlay_lines:
                if re.match(r'^[\d,.]+[KMB]?$', line):
                    num = parse_number(line)
                    if num:
                        standalone_numbers.append(num)
            if len(standalone_numbers) >= 2:
                if not likes:
                    likes = standalone_numbers[0]
                if not comments:
                    comments = standalone_numbers[1]
            elif len(standalone_numbers) == 1:
                if not likes:
                    likes = standalone_numbers[0]
    except:
        pass
    return likes, comments

def hover_scrape_reels(driver, username, first_reel_id, max_reels=100, deep_scrape=False, test_mode=False):
    """
    Infinite scroll-and-scrape. Validates first reel position before starting.
    Modified for deep scrape to go back 2 years.
    """
    profile_url = f"https://www.instagram.com/{username}/reels/"
    driver.get(profile_url)
    time.sleep(5)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)
    if test_mode:
        print(f"\n  🧪 STEP 2: Hover scrape validation (should start at {first_reel_id})...")
    else:
        print(f"  🎯 Step 2: Hover scraping for views/likes/comments (infinite scroll)...")
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
    
    # Calculate cutoff date for deep scrape (2 years ago)
    cutoff_date = datetime.now() - timedelta(days=730)
    
    target_reels = 2000 if deep_scrape else max_reels  # Increased from 500
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
                views = extract_views_from_container(parent)
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(parent).perform()
                    time.sleep(1.1)
                    likes, comments = extract_hover_overlay_data(parent)
                except:
                    likes, comments = None, None
                
                # For deep scrape, check if we need to stop based on position
                # (we can't get dates from hover, so use position as proxy)
                if deep_scrape and len(hover_data) > 730:  # Roughly 2 posts per day for a year
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
                    print(f"    [{len(hover_data)}] {post_id}: {views} views, {likes} likes, {comments} comments")
                elif not test_mode and len(hover_data) % 25 == 0:
                    print(f"    Progress: {len(hover_data)}/{target_reels} reels")
                time.sleep(0.24)
            except Exception as e:
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

def smart_merge_data(hover_data, arrow_data, test_mode=False):
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
        if combined['views'] and combined['likes'] and combined['comments']:
            combined['engagement'] = round(((combined['likes'] + combined['comments']) / combined['views']) * 100, 2)
        else:
            combined['engagement'] = None
        merged.append(combined)
    if test_mode:
        print(f"\n  📊 Merge complete:")
        print(f"     Total reels: {len(merged)}")
        print(f"\n  📋 Final merged reels (ALL {len(merged)} reels):")
        for i, reel in enumerate(merged, 1):
            pinned_marker = " 📌PINNED" if reel.get('is_pinned') else ""
            print(f"     {i}. {reel['reel_id']}{pinned_marker}")
            print(f"        Date: {reel['date_display']}")
            print(f"        Views: {reel['views']}, Likes: {reel['likes']}, Comments: {reel['comments']}")
            print(f"        Engagement: {reel['engagement']}%")
    return merged

def scrape_instagram_account(driver, username, max_reels=100, deep_scrape=False, test_mode=False):
    print(f"  👥 Getting exact follower count...")
    exact_followers = get_exact_follower_count(username)
    if exact_followers:
        print(f"  ✅ Exact follower count: {exact_followers:,}")
    else:
        print(f"  ⚠️  Could not get exact follower count via API, will try Selenium fallback...")
    arrow_data, pinned_count, need_fallback = arrow_scrape_reels(driver, username, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode, use_main_profile=False)
    if need_fallback:
        print(f"\n  🔄 SWITCHING TO MAIN PROFILE for arrow scrape...")
        arrow_data, pinned_count, _ = arrow_scrape_reels(driver, username, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode, use_main_profile=True)
    first_reel_id = arrow_data[0]['reel_id'] if arrow_data else None
    if not first_reel_id:
        print(f"  ❌ Arrow scrape failed - cannot proceed")
        return [], None, 0
    hover_data = hover_scrape_reels(driver, username, first_reel_id, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode)
    final_data = smart_merge_data(hover_data, arrow_data, test_mode=test_mode)
    if exact_followers:
        followers = exact_followers
    else:
        try:
            driver.get(f"https://www.instagram.com/{username}/")
            time.sleep(3)
            followers_elem = driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]/span")
            followers = followers_elem.get_attribute('title') or followers_elem.text
            followers = parse_number(followers.replace(',', ''))
            print(f"  ℹ️  Selenium fallback follower count: {followers:,}")
        except:
            followers = None
            print(f"  ⚠️  Could not retrieve follower count")
    if test_mode:
        print(f"\n  👥 Final Followers: {followers:,}" if followers else "\n  👥 Followers: N/A")
    return final_data, followers, pinned_count

def load_existing_excel():
    import pandas as pd
    if os.path.exists(OUTPUT_EXCEL):
        try:
            excel_data = pd.read_excel(OUTPUT_EXCEL, sheet_name=None, index_col=0)
            return excel_data
        except:
            return {}
    return {}

def create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df=None):
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

def save_to_excel(all_account_data):
    import pandas as pd
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        for username, df in all_account_data.items():
            sheet_name = username[:31]
            df.to_excel(writer, sheet_name=sheet_name)
    print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")

def upload_to_google_drive():
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

def analyze_scrape_quality(scrape_results, expected_reels):
    incomplete_accounts = {}
    for username, result in scrape_results.items():
        reels_actual = result['reels_count']
        # For deep scrape, don't check against expected since it's date-based
        if result.get('deep_scrape'):
            continue
        missing = expected_reels - reels_actual
        if missing > 0 and missing >= (expected_reels * 0.1):
            incomplete_accounts[username] = {
                'reels_expected': expected_reels,
                'reels_actual': reels_actual,
                'missing': missing
            }
    return incomplete_accounts

def rescrape_accounts(driver, incomplete_accounts, existing_data, timestamp_col):
    import pandas as pd
    print("\n" + "="*70)
    print("🔄 RESCRAPING INCOMPLETE ACCOUNTS")
    print("="*70)
    updated_data = {}
    for username, stats in incomplete_accounts.items():
        print(f"\n📱 Rescraping @{username}")
        print(f"  Previous attempt: {stats['reels_actual']}/{stats['reels_expected']} reels")
        print(f"  Missing: {stats['missing']} reels")
        try:
            reels_data, followers, pinned_count = scrape_instagram_account(
                driver, username, 
                max_reels=stats['reels_expected'], 
                deep_scrape=False, 
                test_mode=False
            )
            print(f"\n  ✅ Rescrape complete!")
            print(f"  👥 Followers: {followers:,}" if followers else "  👥 Followers: N/A")
            print(f"  🎬 Reels: {len(reels_data)}")
            existing_df = existing_data.get(username, pd.DataFrame())
            df = create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
            updated_data[username] = df
        except Exception as e:
            print(f"\n  ❌ Rescrape failed for @{username}: {e}")
            if username in existing_data:
                updated_data[username] = existing_data[username]
    return updated_data

def get_scrape_mode():
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

def run_scrape():
    import pandas as pd
    ensure_packages()
    print("\n" + "="*70)
    print("📸 Instagram Reels Analytics Tracker v2.9")
    print("="*70)
    browser_choice = select_browser()
    max_reels, deep_scrape, test_mode = get_scrape_mode()
    if test_mode:
        print("\n🧪 TEST MODE ACTIVATED")
        print(f"   Account: @popdartsgame")
        print(f"   Reels: 15 (will display all 15)")
        print(f"   Browser: {browser_choice.upper()}")
        print(f"   Output: Terminal only (no Excel file)")
        print(f"   Strategy: Arrow FIRST → Hover SECOND → Merge")
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
            expected_reels = None  # Will be determined by date
        else:
            print(f"\n📊 Mode: {max_reels} posts per account")
            expected_reels = max_reels
    input("\n▶️  Press ENTER to start scraping...")
    driver = setup_driver(browser=browser_choice)
    existing_data = load_existing_excel() if not test_mode else {}
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
                reels_data, followers, pinned_count = scrape_instagram_account(
                    driver, username, max_reels=max_reels or 100, deep_scrape=deep_scrape, test_mode=test_mode
                )
                scrape_results[username] = {
                    'reels_count': len(reels_data),
                    'followers': followers,
                    'pinned_count': pinned_count,
                    'deep_scrape': deep_scrape
                }
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
                    views_count = sum(1 for r in reels_data if r['views'])
                    likes_count = sum(1 for r in reels_data if r['likes'])
                    comments_count = sum(1 for r in reels_data if r['comments'])
                    dates_count = sum(1 for r in reels_data if r['date'])
                    print(f"\n   Data coverage:")
                    print(f"     Dates:    {dates_count}/{len(reels_data)} ({dates_count/len(reels_data)*100:.1f}%)")
                    print(f"     Views:    {views_count}/{len(reels_data)} ({views_count/len(reels_data)*100:.1f}%)")
                    print(f"     Likes:    {likes_count}/{len(reels_data)} ({likes_count/len(reels_data)*100:.1f}%)")
                    print(f"     Comments: {comments_count}/{len(reels_data)} ({comments_count/len(reels_data)*100:.1f}%)")
                    print(f"\n💡 This is what will be saved to Excel for each account.")
                    print(f"   Pinned posts are marked with 'is_pinned' = True")
                    print(f"   If this looks good, run again without test mode!")
                    print("="*70 + "\n")
                else:
                    existing_df = existing_data.get(username, pd.DataFrame())
                    df = create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
                    all_account_data[username] = df
                    print(f"\n  ✅ @{username} complete!")
                    print(f"  👥 Followers: {followers:,}" if followers else "  👥 Followers: N/A")
                    if deep_scrape:
                        if reels_data:
                            # Calculate how far back we went
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
                        print(f"  🎬 Reels: {len(reels_data)}/{expected_reels} (including {pinned_count} pinned)")
            except Exception as e:
                print(f"\n  ❌ Error with @{username}: {e}")
                import traceback
                traceback.print_exc()
                scrape_results[username] = {
                    'reels_count': 0,
                    'followers': None,
                    'pinned_count': 0,
                    'deep_scrape': deep_scrape
                }
                continue
        if not test_mode:
            save_to_excel(all_account_data)
            upload_success = upload_to_google_drive()
            
            # Only analyze quality for non-deep scrapes
            if not deep_scrape and expected_reels:
                incomplete_accounts = analyze_scrape_quality(scrape_results, expected_reels)
                if incomplete_accounts:
                    print("\n" + "="*70)
                    print("⚠️  INCOMPLETE SCRAPES DETECTED")
                    print("="*70)
                    for username, stats in incomplete_accounts.items():
                        print(f"\n  @{username}:")
                        print(f"    Expected: {stats['reels_expected']} reels")
                        print(f"    Got: {stats['reels_actual']} reels")
                        print(f"    Missing: {stats['missing']} reels")
                    print("\n" + "="*70)
                    rescrape = input("\n🔄 Would you like to rescrape incomplete accounts? (y/n): ").strip().lower()
                    if rescrape == 'y':
                        updated_accounts = rescrape_accounts(driver, incomplete_accounts, all_account_data, timestamp_col)
                        for username, df in updated_accounts.items():
                            all_account_data[username] = df
                        print("\n💾 Updating Excel with rescraped data...")
                        save_to_excel(all_account_data)
                        print("\n☁️  Re-uploading updated file to Google Drive...")
                        upload_to_google_drive()
                        print("\n" + "="*70)
                        print("✅ Rescrape complete! File updated on Google Drive.")
                        print("="*70)
                    else:
                        print("\n⏭️  Skipping rescrape. Initial data has been saved and uploaded.")
            
            # Check for missing hover data
            incomplete_hover = {}
            for username, df in all_account_data.items():
                reel_rows = [row for row in df.index if row.startswith('reel_') and row.endswith('_views')]
                missing_count = 0
                for row in reel_rows:
                    views = df.loc[row, timestamp_col]
                    if views is None or pd.isna(views):
                        missing_count += 1
                if missing_count > 0:
                    incomplete_hover[username] = missing_count
            if incomplete_hover:
                print("\n⚠️  Missing hover data detected:")
                for username, count in incomplete_hover.items():
                    print(f"  @{username}: {count} reels without views/likes/comments")
                rescrape_hover = input("\n🔄 Would you like to rescrape to get hover data for these missing posts? (y/n): ").strip().lower()
                if rescrape_hover == 'y':
                    for username in incomplete_hover:
                        print(f"\n🔄 Rescraping @{username} for hover data...")
                        try:
                            reels_data, followers, pinned_count = scrape_instagram_account(
                                driver, username, max_reels=expected_reels or 100, deep_scrape=deep_scrape, test_mode=False
                            )
                            existing_df = all_account_data[username]
                            df = create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
                            all_account_data[username] = df
                            print(f"  ✅ Hover rescrape complete for @{username}!")
                        except Exception as e:
                            print(f"❌ Rescrape failed for @{username}: {e}")
                    print("\n💾 Updating Excel with hover rescraped data...")
                    save_to_excel(all_account_data)
                    print("\n☁️  Re-uploading updated file to Google Drive...")
                    upload_to_google_drive()
                    print("\n" + "="*70)
                    print("✅ Hover rescrape complete! File updated on Google Drive.")
                    print("="*70)
                else:
                    print("\n⏭️  Skipping hover rescrape. Data saved as is.")
            print("\n" + "="*70)
            print("✅ All scraping complete!")
            print(f"📁 Local file: '{OUTPUT_EXCEL}'")
            print(f"🌐 View analytics: https://crespo.world/crespomize.html")
            print("="*70 + "\n")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scrape()
