#!/usr/bin/env python3
"""
Multi-Account Instagram Reels Analytics Tracker
- Scrapes multiple Instagram accounts for Reels data
- Uses hybrid method: hover scrape + arrow key navigation
- Auto-detects and skips pinned posts
- Updates Excel file with separate tabs for each account
- Cross-validates likes/comments from both methods
- NEW: Choose custom post count or deep scrape mode
"""

import sys
import subprocess
import os
from datetime import datetime
import time
import re
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

# Instagram cookies from Firefox
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
            install_package(p)
        print("✅ All packages installed!")


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
# Hover scrape method
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
        
        # Method 1: Look for explicit "X likes" and "X comments"
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
        
        # Method 2: Standalone numbers side-by-side
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


def hover_scrape_reels(driver, username, max_reels=25, deep_scrape=False):
    """Scrape reels using hover method"""
    reels_url = f"https://www.instagram.com/{username}/reels/"
    driver.get(reels_url)
    time.sleep(5)
    
    # Scroll to load more reels
    scroll_iterations = 20 if deep_scrape else 4
    for _ in range(scroll_iterations):
        driver.execute_script("window.scrollBy(0, 800)")
        time.sleep(1.5)
    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(2)
    
    reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
    
    hover_data = []
    
    reels_to_scrape = len(reel_links) if deep_scrape else min(max_reels, len(reel_links))
    
    for idx in range(reels_to_scrape):
        try:
            reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
            if idx >= len(reel_links):
                break
            
            reel_link = reel_links[idx]
            reel_url = reel_link.get_attribute('href')
            reel_id = reel_url.split('/reel/')[-1].rstrip('/')
            
            parent = reel_link.find_element(By.XPATH, "..")
            views = extract_views_from_container(parent)
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", parent)
            time.sleep(0.6)
            
            actions = ActionChains(driver)
            actions.move_to_element(parent).perform()
            time.sleep(2.5)
            
            likes, comments = extract_hover_overlay_data(parent)
            
            hover_data.append({
                'reel_id': reel_id,
                'views': views,
                'likes': likes,
                'comments': comments,
                'position': idx
            })
            
            time.sleep(0.3)
            
        except:
            continue
    
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


def arrow_scrape_reels(driver, username, max_reels=25, deep_scrape=False):
    """Scrape reels using arrow keys"""
    reels_url = f"https://www.instagram.com/{username}/reels/"
    driver.get(reels_url)
    time.sleep(5)
    
    reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reel/')]")
    if not reel_links:
        return [], 0
    
    driver.execute_script("arguments[0].click();", reel_links[0])
    time.sleep(3)
    
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
            
            if deep_scrape and idx % 10 == 0:
                print(f"    Progress: {idx + 1} reels scraped...")
            
            if idx < max_iterations - 1:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(1.5)
        except:
            if deep_scrape:
                print(f"    Reached end at {idx + 1} reels")
            break
    
    return arrow_data, pinned_count


# -------------------------
# Merge data
# -------------------------
def merge_data(hover_data, arrow_data, pinned_count):
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
        
        # Prefer higher number for likes (as per your request)
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
    
    return merged


# -------------------------
# Scrape account
# -------------------------
def scrape_instagram_account(driver, username, max_reels=18, deep_scrape=False):
    """Scrape a single Instagram account"""
    print(f"\n  📊 Hover scraping @{username}...")
    hover_data = hover_scrape_reels(driver, username, max_reels=max_reels if not deep_scrape else 500, deep_scrape=deep_scrape)
    print(f"  ✅ Hover complete: {len(hover_data)} reels")
    
    print(f"  📅 Arrow key scraping @{username}...")
    arrow_data, pinned_count = arrow_scrape_reels(driver, username, max_reels=max_reels, deep_scrape=deep_scrape)
    print(f"  ✅ Arrow complete: {len(arrow_data)} reels")
    
    if pinned_count > 0:
        print(f"  📌 Skipped {pinned_count} pinned post(s)")
    
    final_data = merge_data(hover_data, arrow_data, pinned_count)
    
    # Get follower count
    try:
        driver.get(f"https://www.instagram.com/{username}/")
        time.sleep(3)
        followers_elem = driver.find_element(By.XPATH, "//a[contains(@href, '/followers/')]/span")
        followers = followers_elem.get_attribute('title') or followers_elem.text
        followers = parse_number(followers.replace(',', ''))
    except:
        followers = None
    
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
    print("\n" + "="*60)
    print("☁️  Uploading to Google Drive...")
    print("="*60)
    
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
# User input
# -------------------------
def get_scrape_mode():
    """Ask user for scrape mode"""
    print("\n" + "="*60)
    print("🎯 SELECT SCRAPE MODE")
    print("="*60)
    print("\n1. Custom number of posts")
    print("2. Deep scrape (all available posts)")
    print()
    
    while True:
        choice = input("Enter your choice (1 or 2): ").strip()
        if choice == '1':
            while True:
                try:
                    num_posts = int(input("\nHow many posts do you want to scrape per account? "))
                    if num_posts > 0:
                        return num_posts, False
                    else:
                        print("Please enter a positive number.")
                except ValueError:
                    print("Please enter a valid number.")
        elif choice == '2':
            confirm = input("\n⚠️  Deep scrape may take a long time. Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                return None, True
            else:
                continue
        else:
            print("Invalid choice. Please enter 1 or 2.")


# -------------------------
# Main
# -------------------------
def run_scrape():
    """Main scrape function"""
    import pandas as pd
    
    ensure_packages()
    
    print("\n" + "="*60)
    print("📸 Instagram Reels Analytics Tracker")
    print("="*60)
    
    print(f"\n✅ Will scrape {len(ACCOUNTS_TO_TRACK)} account(s):\n")
    for i, account in enumerate(ACCOUNTS_TO_TRACK, 1):
        print(f"   {i}. @{account}")
    
    max_reels, deep_scrape = get_scrape_mode()
    
    if deep_scrape:
        print("\n🔍 Mode: DEEP SCRAPE (all posts)")
    else:
        print(f"\n📊 Mode: {max_reels} posts per account")
    
    input("\n▶️  Press ENTER to start scraping...")
    
    driver = setup_driver()
    
    existing_data = load_existing_excel()
    timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_account_data = {}
    
    try:
        for idx, username in enumerate(ACCOUNTS_TO_TRACK, 1):
            print("\n" + "="*60)
            print(f"📱 [{idx}/{len(ACCOUNTS_TO_TRACK)}] Processing @{username}")
            print("="*60)
            
            try:
                reels_data, followers, pinned_count = scrape_instagram_account(
                    driver, username, max_reels=max_reels or 18, deep_scrape=deep_scrape
                )
                
                existing_df = existing_data.get(username, pd.DataFrame())
                df = create_dataframe_for_account(reels_data, followers, timestamp_col, existing_df)
                all_account_data[username] = df
                
                print(f"\n  ✅ @{username} complete!")
                print(f"  👥 Followers: {followers:,}" if followers else "  👥 Followers: N/A")
                print(f"  🎬 Reels: {len(reels_data)}")
                
            except Exception as e:
                print(f"\n  ❌ Error with @{username}: {e}")
                continue
        
        save_to_excel(all_account_data)
        
        # Upload to Google Drive
        upload_to_google_drive()
        
        print("\n" + "="*60)
        print("✅ All accounts scraped successfully!")
        print(f"📁 Created: '{OUTPUT_EXCEL}'")
        print("="*60 + "\n")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    run_scrape()
