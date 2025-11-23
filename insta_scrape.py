#!/usr/bin/env python3
"""
Instagram Reels Analytics Tracker v2.2
- FIXED: Continuous scroll for hover scrape (no snap back!)
- Hybrid method: hover scrape + arrow key navigation
- Auto-detects and skips pinned posts
- Updates Excel with separate tabs per account
- Cross-validates likes/comments from both methods
- Auto-uploads to Google Drive
- NEW: Gets exact follower count via Instagram API
- NEW: Auto-detects incomplete scrapes and offers to rescrape
- TEST MODE: Try 30 reels on @popdartsgame first
"""

import sys
import subprocess
import os
from datetime import datetime
import time
import re
import requests
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

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

# Instagram cookies
INSTAGRAM_COOKIES = [
    {'name': 'sessionid', 'value': '8438482535%3A38IX9Bm9deq9jo%3A17%3AAYiVmEzuyxxTnjyeCI9hapArXNlkzUnBss_8pz4EJg', 'domain': '.instagram.com'},
    {'name': 'csrftoken', 'value': 'R81AQp-PTmKwPM1DIeNHN-', 'domain': '.instagram.com'},
    {'name': 'ds_user_id', 'value': '8438482535', 'domain': '.instagram.com'},
    {'name': 'mid', 'value': 'aRqN7gALAAFE_ZLG2YR4s_jAJbWN', 'domain': '.instagram.com'},
    {'name': 'ig_did', 'value': 'C4BB1B54-EE7F-44CE-839C-A6522013D97A', 'domain': '.instagram.com'},
    {'name': 'datr', 'value': '7Y0aabbcI4vK3rldO6uL60Mr', 'domain': '.instagram.com'},
    {'name': 'rur', 'value': '"RVA\0548438482535\0541795318515:01fed47cf9a9228eedfc2a590e74f4dad85f30cd9b792690568dcd882909ab747dff45ca"', 'domain': '.instagram.com'},
]


# -------------------------
# Package helpers
# -------------------------
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


# -------------------------
# EXACT FOLLOWER COUNT (from instagram_follower_scraper.py)
# -------------------------
def get_exact_follower_count(username):
    """
    Fetch the exact follower count for an Instagram username using Instagram API
    
    Args:
        username: Instagram username (without @)
    
    Returns:
        int: exact follower count, or None if failed
    """
    # Remove @ if user included it
    username = username.replace('@', '')
    
    # Instagram's web profile info endpoint
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    
    # Headers to mimic Instagram's mobile app
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
        
        # Extract user data
        user_data = data['data']['user']
        follower_count = user_data['edge_followed_by']['count']
        
        return follower_count
        
    except requests.exceptions.RequestException as e:
        print(f"    ⚠️  API request failed: {e}")
        return None
    except KeyError as e:
        print(f"    ⚠️  Failed to parse follower count from API")
        return None
    except Exception as e:
        print(f"    ⚠️  Unexpected error getting follower count: {e}")
        return None


# -------------------------
# Utility functions
# -------------------------
def parse_number(text):
    """Convert Instagram number format to integer"""
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
    """Convert Instagram date to comparable timestamp"""
    if not date_str:
        return None
    
    try:
        if 'T' in date_str:
            date_str = date_str.replace('Z', '').split('.')[0]
            return datetime.fromisoformat(date_str)
    except:
        pass
    
    return None


# -------------------------
# Driver setup
# -------------------------
def setup_driver():
    """Setup Firefox with cookies"""
    from webdriver_manager.firefox import GeckoDriverManager
    
    print("  🦊 Setting up Firefox driver...")
    
    firefox_options = Options()
    firefox_options.set_preference("general.useragent.override", 
                                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0")
    
    service = Service(GeckoDriverManager().install())
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


# -------------------------
# Hover scrape method - FIXED WITH CONTINUOUS SCROLL
# -------------------------
def extract_views_from_container(container):
    """Extract view count from container"""
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
    """Extract likes and comments from hover overlay"""
    likes = None
    comments = None
    
    try:
        overlay_text = parent.text
        overlay_lines = [line.strip() for line in overlay_text.split('\n') if line.strip()]
        
        for line in overlay_lines:
            line_lower = line.lower()
            
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


def hover_scrape_reels(driver, username, max_reels=100, deep_scrape=False, test_mode=False):
    """
    Scrape reels using hover method - FIXED VERSION
    - Scrolls AND hovers simultaneously (no snap back to top)
    - Processes reels as they become visible
    """
    reels_url = f"https://www.instagram.com/{username}/reels/"
    driver.get(reels_url)
    time.sleep(5)
    
    # Start at top
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)
    
    target_reels = 500 if deep_scrape else max_reels
    hover_data = []
    processed_reel_ids = set()
    consecutive_no_progress = 0
    
    if test_mode:
        print(f"\n  🧪 TEST MODE: Hover scraping {target_reels} reels...")
    else:
        print(f"  🎯 Hover scraping (target: {target_reels} reels)...")
    
    while len(hover_data) < target_reels:
        # Stop if no progress for too long
        if consecutive_no_progress >= 15:
            if test_mode:
                print(f"    ✅ Reached end at {len(hover_data)} reels")
            break
        
        # Get currently visible reel links
        reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
        
        new_reels_this_cycle = 0
        
        for reel_link in reel_links:
            if len(hover_data) >= target_reels:
                break
            
            try:
                reel_url = reel_link.get_attribute('href')
                if not reel_url or '/reel/' not in reel_url:
                    continue
                
                reel_id = reel_url.split('/reel/')[-1].rstrip('/').split('?')[0]
                
                # Skip if already processed
                if reel_id in processed_reel_ids:
                    continue
                
                # Check if element is visible in viewport
                is_visible = driver.execute_script(
                    "var rect = arguments[0].getBoundingClientRect();"
                    "return (rect.top >= 0 && rect.top < window.innerHeight - 100);",
                    reel_link
                )
                
                if not is_visible:
                    continue
                
                # Process this reel
                parent = reel_link.find_element(By.XPATH, "..")
                
                # Get views
                views = extract_views_from_container(parent)
                
                # Hover for likes/comments
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(parent).perform()
                    time.sleep(2.0)
                    likes, comments = extract_hover_overlay_data(parent)
                except:
                    likes, comments = None, None
                
                hover_data.append({
                    'reel_id': reel_id,
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'position': len(hover_data)
                })
                
                processed_reel_ids.add(reel_id)
                new_reels_this_cycle += 1
                
                # Progress updates
                if test_mode and len(hover_data) <= 10:
                    print(f"    [{len(hover_data)}] {reel_id}: {views} views, {likes} likes, {comments} comments")
                elif not test_mode and len(hover_data) % 25 == 0:
                    print(f"    Progress: {len(hover_data)}/{target_reels} reels")
                
                time.sleep(0.2)
                
            except:
                continue
        
        # Track progress
        if new_reels_this_cycle > 0:
            consecutive_no_progress = 0
        else:
            consecutive_no_progress += 1
        
        # Scroll down to load more (NEVER scroll back up!)
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(0.5)
        
        # If no progress, scroll more aggressively
        if new_reels_this_cycle == 0:
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(0.3)
    
    if test_mode:
        print(f"\n  📊 Hover scrape complete: {len(hover_data)} reels")
    
    return hover_data


# -------------------------
# Arrow key scrape method
# -------------------------
def extract_reel_data_from_overlay(driver):
    """Extract data from open reel overlay"""
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
    """Detect pinned posts by comparing dates"""
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


def arrow_scrape_reels(driver, username, max_reels=100, deep_scrape=False, test_mode=False):
    """Scrape reels using arrow keys"""
    reels_url = f"https://www.instagram.com/{username}/reels/"
    driver.get(reels_url)
    time.sleep(5)
    
    reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
    if not reel_links:
        return [], 0
    
    driver.execute_script("arguments[0].click();", reel_links[0])
    time.sleep(3)
    
    if test_mode:
        print(f"\n  🧪 TEST MODE: Arrow scraping for dates...")
    else:
        print(f"  📅 Arrow key scraping for dates...")
    
    # Detect pinned posts
    initial_reels = []
    for idx in range(min(5, max_reels)):
        try:
            time.sleep(1)
            data = extract_reel_data_from_overlay(driver)
            initial_reels.append(data)
            
            if idx < 4:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(1.5)
        except:
            break
    
    pinned_count = detect_pinned_posts(initial_reels)
    
    if test_mode and pinned_count > 0:
        print(f"    📌 Detected {pinned_count} pinned post(s)")
    
    # Navigate to organic posts
    if pinned_count > 0:
        for _ in range(len(initial_reels) - 1):
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ARROW_LEFT)
            time.sleep(0.8)
        
        for _ in range(pinned_count):
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ARROW_RIGHT)
            time.sleep(1)
    else:
        for _ in range(len(initial_reels) - 1):
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ARROW_LEFT)
            time.sleep(0.8)
    
    # Extract organic posts
    arrow_data = []
    max_iterations = 500 if deep_scrape else max_reels
    
    for idx in range(max_iterations):
        try:
            time.sleep(1)
            data = extract_reel_data_from_overlay(driver)
            arrow_data.append(data)
            
            # Progress updates
            if test_mode and idx < 10:
                reel_id = data.get('reel_id', 'N/A')
                date = data.get('date_display', 'N/A')
                likes = data.get('likes', 'N/A')
                print(f"    [{idx+1}] {reel_id}: {date}, {likes} likes")
            elif not test_mode and deep_scrape and idx % 25 == 0:
                print(f"    Arrow progress: {idx + 1}/{max_iterations} reels...")
            
            if idx < max_iterations - 1:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(1.5)
        except:
            if test_mode:
                print(f"    ✅ Arrow scrape complete: {idx + 1} reels")
            break
    
    if test_mode:
        print(f"\n  📊 Arrow scrape complete: {len(arrow_data)} reels")
    
    return arrow_data, pinned_count


# -------------------------
# Merge data
# -------------------------
def merge_data(hover_data, arrow_data, pinned_count, test_mode=False):
    """Merge hover and arrow data"""
    merged = []
    
    for arrow_idx, arrow_reel in enumerate(arrow_data):
        hover_idx = arrow_idx + pinned_count
        
        hover_reel = None
        for h in hover_data:
            if h['reel_id'] == arrow_reel['reel_id']:
                hover_reel = h
                break
        
        if not hover_reel and hover_idx < len(hover_data):
            hover_reel = hover_data[hover_idx]
        
        # Prefer higher number for likes
        likes_hover = hover_reel.get('likes') if hover_reel else None
        likes_arrow = arrow_reel.get('likes')
        
        if likes_hover and likes_arrow:
            final_likes = max(likes_hover, likes_arrow)
        else:
            final_likes = likes_arrow or likes_hover
        
        # Same for comments - prefer higher
        comments_hover = hover_reel.get('comments') if hover_reel else None
        comments_arrow = arrow_reel.get('comments')
        
        if comments_hover and comments_arrow:
            final_comments = max(comments_hover, comments_arrow)
        else:
            final_comments = comments_arrow or comments_hover
        
        combined = {
            'reel_id': arrow_reel['reel_id'],
            'position': arrow_idx + 1,
            'date': arrow_reel.get('date'),
            'date_display': arrow_reel.get('date_display'),
            'views': hover_reel.get('views') if hover_reel else None,
            'likes': final_likes,
            'comments': final_comments,
        }
        
        if combined['views'] and combined['likes'] and combined['comments']:
            combined['engagement'] = round(((combined['likes'] + combined['comments']) / combined['views']) * 100, 2)
        else:
            combined['engagement'] = None
        
        merged.append(combined)
    
    if test_mode:
        print(f"\n  🔗 Merged data:")
        print(f"     Total reels: {len(merged)}")
        print(f"\n  📋 Sample merged reels (first 5):")
        for i, reel in enumerate(merged[:5], 1):
            print(f"     {i}. {reel['reel_id']}")
            print(f"        Date: {reel['date_display']}")
            print(f"        Views: {reel['views']}, Likes: {reel['likes']}, Comments: {reel['comments']}")
            print(f"        Engagement: {reel['engagement']}%")
    
    return merged


# -------------------------
# Scrape account
# -------------------------
def scrape_instagram_account(driver, username, max_reels=100, deep_scrape=False, test_mode=False):
    """Scrape a single Instagram account"""
    
    # Get exact follower count FIRST using API
    print(f"  👥 Getting exact follower count...")
    exact_followers = get_exact_follower_count(username)
    
    if exact_followers:
        print(f"  ✅ Exact follower count: {exact_followers:,}")
    else:
        print(f"  ⚠️  Could not get exact follower count via API, will try Selenium fallback...")
    
    hover_data = hover_scrape_reels(driver, username, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode)
    
    arrow_data, pinned_count = arrow_scrape_reels(driver, username, max_reels=max_reels, deep_scrape=deep_scrape, test_mode=test_mode)
    
    if pinned_count > 0 and not test_mode:
        print(f"  📌 Skipped {pinned_count} pinned post(s)")
    
    final_data = merge_data(hover_data, arrow_data, pinned_count, test_mode=test_mode)
    
    # Use exact follower count if we got it, otherwise fallback to Selenium scrape
    if exact_followers:
        followers = exact_followers
    else:
        # Fallback: Try to get follower count from profile page
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


# -------------------------
# Excel helpers
# -------------------------
def load_existing_excel():
    """Load existing Excel file"""
    import pandas as pd
    
    if os.path.exists(OUTPUT_EXCEL):
        try:
            excel_data = pd.read_excel(OUTPUT_EXCEL, sheet_name=None, index_col=0)
            return excel_data
        except:
            return {}
    return {}


def create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df=None):
    """Create or update DataFrame for account"""
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
        for metric in ['date', 'date_display', 'views', 'likes', 'comments', 'engagement']:
            row_name = f"reel_{reel_id}_{metric}"
            if row_name not in df.index:
                df.loc[row_name] = None
            df.loc[row_name, timestamp_col] = reel.get(metric, "")
    
    return df


def save_to_excel(all_account_data):
    """Save to Excel"""
    import pandas as pd
    
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        for username, df in all_account_data.items():
            sheet_name = username[:31]
            df.to_excel(writer, sheet_name=sheet_name)
    
    print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")


# -------------------------
# Upload to Google Drive
# -------------------------
def upload_to_google_drive():
    """Upload Excel file to Google Drive using rclone"""
    print("\n" + "="*70)
    print("☁️  Uploading to Google Drive...")
    print("="*70)
    
    try:
        # Check if rclone is installed
        result = subprocess.run(['rclone', 'version'], 
                              capture_output=True, 
                              text=True)
        
        if result.returncode != 0:
            print("❌ rclone not found. Please install rclone first.")
            print("   Visit: https://rclone.org/downloads/")
            return False
        
        # Get the full path to the Excel file
        excel_path = os.path.abspath(OUTPUT_EXCEL)
        
        # Upload using rclone
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


# -------------------------
# RESCRAPE FUNCTIONALITY
# -------------------------
def analyze_scrape_quality(scrape_results, expected_reels):
    """
    Analyze scrape results and identify incomplete accounts
    
    Returns:
        dict: {username: {'reels_expected': int, 'reels_actual': int, 'missing': int}}
    """
    incomplete_accounts = {}
    
    for username, result in scrape_results.items():
        reels_actual = result['reels_count']
        missing = expected_reels - reels_actual
        
        # Consider incomplete if missing more than 10% of expected reels
        if missing > 0 and missing >= (expected_reels * 0.1):
            incomplete_accounts[username] = {
                'reels_expected': expected_reels,
                'reels_actual': reels_actual,
                'missing': missing
            }
    
    return incomplete_accounts


def rescrape_accounts(driver, incomplete_accounts, existing_data, timestamp_col):
    """
    Rescrape incomplete accounts and merge with existing data
    
    Returns:
        dict: updated account data
    """
    import pandas as pd
    
    print("\n" + "="*70)
    print("🔄 RESCRAPIN INCOMPLETE ACCOUNTS")
    print("="*70)
    
    updated_data = {}
    
    for username, stats in incomplete_accounts.items():
        print(f"\n📱 Rescaping @{username}")
        print(f"  Previous attempt: {stats['reels_actual']}/{stats['reels_expected']} reels")
        print(f"  Missing: {stats['missing']} reels")
        
        try:
            # Rescrape with same parameters
            reels_data, followers, pinned_count = scrape_instagram_account(
                driver, username, 
                max_reels=stats['reels_expected'], 
                deep_scrape=False, 
                test_mode=False
            )
            
            print(f"\n  ✅ Rescrape complete!")
            print(f"  👥 Followers: {followers:,}" if followers else "  👥 Followers: N/A")
            print(f"  🎬 Reels: {len(reels_data)}")
            
            # Update the existing dataframe
            existing_df = existing_data.get(username, pd.DataFrame())
            df = create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
            updated_data[username] = df
            
        except Exception as e:
            print(f"\n  ❌ Rescrape failed for @{username}: {e}")
            # Keep the old data if rescrape fails
            if username in existing_data:
                updated_data[username] = existing_data[username]
    
    return updated_data


# -------------------------
# User input
# -------------------------
def get_scrape_mode():
    """Ask user for scrape mode"""
    print("\n" + "="*70)
    print("🎯 SELECT SCRAPE MODE")
    print("="*70)
    print("\n1. Custom number of posts (default: 100)")
    print("2. Deep scrape (up to 500 posts)")
    print("3. Test mode (30 reels on @popdartsgame, no file created)")
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
            confirm = input("\n⚠️  Deep scrape may take a while. Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                return None, True, False
            else:
                continue
        
        elif choice == '3':
            return 30, False, True
        
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


# -------------------------
# Main
# -------------------------
def run_scrape():
    """Main scrape function"""
    import pandas as pd
    
    ensure_packages()
    
    print("\n" + "="*70)
    print("📸 Instagram Reels Analytics Tracker v2.2")
    print("="*70)
    
    max_reels, deep_scrape, test_mode = get_scrape_mode()
    
    if test_mode:
        print("\n🧪 TEST MODE ACTIVATED")
        print(f"   Account: @popdartsgame")
        print(f"   Reels: 30")
        print(f"   Output: Terminal only (no Excel file)")
        accounts = ["popdartsgame"]
    else:
        print(f"\n✅ Will scrape {len(ACCOUNTS_TO_TRACK)} account(s):\n")
        for i, account in enumerate(ACCOUNTS_TO_TRACK, 1):
            print(f"   {i}. @{account}")
        accounts = ACCOUNTS_TO_TRACK
    
    if deep_scrape:
        print("\n🔍 Mode: DEEP SCRAPE (up to 500 posts)")
        expected_reels = 500
    elif not test_mode:
        print(f"\n📊 Mode: {max_reels} posts per account")
        expected_reels = max_reels
    else:
        expected_reels = 30
    
    input("\n▶️  Press ENTER to start scraping...")
    
    driver = setup_driver()
    
    existing_data = load_existing_excel() if not test_mode else {}
    timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_account_data = {}
    scrape_results = {}  # Track scrape results for quality analysis
    
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
                
                # Track results
                scrape_results[username] = {
                    'reels_count': len(reels_data),
                    'followers': followers,
                    'pinned_count': pinned_count
                }
                
                if test_mode:
                    # Test mode: just print summary
                    print("\n" + "="*70)
                    print("✅ TEST COMPLETE!")
                    print("="*70)
                    print(f"\n📊 Summary:")
                    print(f"   Account: @{username}")
                    print(f"   Followers: {followers:,}" if followers else "   Followers: N/A")
                    print(f"   Reels scraped: {len(reels_data)}")
                    print(f"   Pinned posts: {pinned_count}")
                    
                    # Data quality
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
                    print(f"   If this looks good, run again without test mode!")
                    print("="*70 + "\n")
                    
                else:
                    # Normal mode: save to Excel
                    existing_df = existing_data.get(username, pd.DataFrame())
                    df = create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
                    all_account_data[username] = df
                    
                    print(f"\n  ✅ @{username} complete!")
                    print(f"  👥 Followers: {followers:,}" if followers else "  👥 Followers: N/A")
                    print(f"  🎬 Reels: {len(reels_data)}/{expected_reels}")
                
            except Exception as e:
                print(f"\n  ❌ Error with @{username}: {e}")
                import traceback
                traceback.print_exc()
                
                # Track failed scrapes
                scrape_results[username] = {
                    'reels_count': 0,
                    'followers': None,
                    'pinned_count': 0
                }
                continue
        
        if not test_mode:
            # Save initial Excel
            save_to_excel(all_account_data)
            
            # Upload to Google Drive
            upload_success = upload_to_google_drive()
            
            # Analyze scrape quality
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
                    # Rescrape incomplete accounts
                    updated_accounts = rescrape_accounts(driver, incomplete_accounts, all_account_data, timestamp_col)
                    
                    # Merge updated data with existing
                    for username, df in updated_accounts.items():
                        all_account_data[username] = df
                    
                    # Save updated Excel
                    print("\n💾 Updating Excel with rescraped data...")
                    save_to_excel(all_account_data)
                    
                    # Re-upload to Google Drive
                    print("\n☁️  Re-uploading updated file to Google Drive...")
                    upload_to_google_drive()
                    
                    print("\n" + "="*70)
                    print("✅ Rescrape complete! File updated on Google Drive.")
                    print("="*70)
                else:
                    print("\n⏭️  Skipping rescrape. Initial data has been saved and uploaded.")
            
            print("\n" + "="*70)
            print("✅ All scraping complete!")
            print(f"📁 Local file: '{OUTPUT_EXCEL}'")
            print(f"🌐 View analytics: https://crespo.world/crespomize.html")
            print("="*70 + "\n")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    run_scrape()
