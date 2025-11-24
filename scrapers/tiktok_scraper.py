#!/usr/bin/env python3
"""
Multi-Account TikTok Analytics Tracker
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
from datetime import datetime
import statistics
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image
import pytesseract
import time

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

OUTPUT_EXCEL = "tiktok_analytics_tracker.xlsx"


# -------------------------
# Package helpers
# -------------------------
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

def ensure_packages():
    packages_needed = []
    required = {
        'yt_dlp': 'yt-dlp',
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
# Auto-detect accounts from Excel
# -------------------------
def get_accounts_from_excel():
    """Auto-detect all account names from existing Excel file"""
    import pandas as pd
    
    if not os.path.exists(OUTPUT_EXCEL):
        print(f"❌ Excel file not found: {OUTPUT_EXCEL}")
        return None
    
    try:
        # Read all sheet names
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


# -------------------------
# TokCount Scraper (Fast followers/likes)
# -------------------------
def get_tokcount_stats(username):
    """
    Get followers and likes for a TikTok user from TokCount using screenshots + OCR
    """
    url = f"https://tokcount.com/?user={username}"
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--headless")
    
    print(f"  🔍 Fetching TokCount stats...")
    driver = webdriver.Chrome(options=chrome_options)
    
screenshot_files = []
    
    try:
        driver.get(url)
        time.sleep(8)  # Wait for page to load
        
        # Take screenshots at different scroll positions
        scroll_positions = [0, 200, 400, 600, 800]
        
        for i, scroll_pos in enumerate(scroll_positions):
            driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
            time.sleep(1)
            filename = os.path.join(desktop_path, f"tokcount_temp_{username}_{i+1}.png")
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
        driver.quit()
        # Clean up screenshots
        for filename in screenshot_files:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass


# -------------------------
# yt-dlp Scraper (Detailed per-post)
# -------------------------
def scrape_tiktok_profile(username, max_videos=100):
    """
    Returns (videos_data, follower_count, total_likes)
    videos_data includes Date, Views, Likes, Comments, Shares, EngagementRate
    """
    import yt_dlp
    from datetime import datetime as _dt

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

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        profile_url = f"https://www.tiktok.com/@{username}"
        try:
            playlist_info = ydl.extract_info(profile_url, download=False)
        except Exception:
            ydl_opts['extract_flat'] = True
            with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                playlist_info = ydl2.extract_info(profile_url, download=False)

        if not playlist_info:
            print("  ❌ Could not access profile")
            return [], None, None

        follower_count = playlist_info.get('channel_follower_count') or \
                         playlist_info.get('followers') or 0
        total_likes_estimate = playlist_info.get('channel_like_count') or \
                               playlist_info.get('like_count') or 0

        entries = playlist_info.get('entries', [])
        if not entries and 'url' in playlist_info:
            entries = [playlist_info]

        posts_to_scrape = entries if max_videos == 9999999 else entries[:max_videos]

        for i, entry in enumerate(posts_to_scrape):
            try:
                if isinstance(entry, dict) and entry.get('_type') == 'url':
                    with yt_dlp.YoutubeDL({'quiet': True, 'ignoreerrors': True}) as ydl_single:
                        video_info = ydl_single.extract_info(entry['url'], download=False)
                else:
                    video_info = entry
                if not video_info:
                    continue

                video_id = video_info.get('id', f"unknown_{i}")
                views = video_info.get('view_count', 0) or 0
                likes = video_info.get('like_count', 0) or 0
                comments = video_info.get('comment_count', 0) or 0
                shares = video_info.get('repost_count', 0) or 0
                upload_date = video_info.get('upload_date')
                if upload_date and len(upload_date) == 8:
                    date_obj = _dt.strptime(upload_date, "%Y%m%d")
                else:
                    date_obj = _dt.now()
                engagement = (likes + comments) / views * 100 if views > 0 else 0

                videos_data.append({
                    'VideoID': video_id,
                    'Date': date_obj.strftime('%Y-%m-%d'),
                    'Views': views,
                    'Likes': likes,
                    'Comments': comments,
                    'Shares': shares,
                    'EngagementRate': round(engagement, 2)
                })
            except Exception as e:
                print(f"  ⚠️ Skipping a video due to error: {e}")
                continue

    print(f"  ✅ Scraped {len(videos_data)} videos")
    return videos_data, int(follower_count), int(total_likes_estimate)


# -------------------------
# Excel helpers
# -------------------------
def load_existing_excel():
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


def create_dataframe_for_account(videos_data, followers, total_likes, timestamp_col, existing_df=None):
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


def save_to_excel(all_account_data):
    """Save all account data to multi-tab Excel file"""
    import pandas as pd
    
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        for username, df in all_account_data.items():
            # Excel sheet names can't exceed 31 chars
            sheet_name = username[:31]
            df.to_excel(writer, sheet_name=sheet_name)
    
    print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")


# -------------------------
# Dashboard
# -------------------------
def show_account_summary(username, df):
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


# -------------------------
# Get scrape configuration
# -------------------------
def get_scrape_config():
    """Ask user for scrape configuration at the start"""
    print("\n" + "="*60)
    print("⚙️  SCRAPE CONFIGURATION")
    print("="*60)
    
    while True:
        print("\nHow many posts would you like to scrape per account?")
        print("  • Enter a number (default: 100)")
        print("  • Type 'deep' for maximum scrape (all available)")
        
        user_input = input("\n📊 Posts to scrape [100]: ").strip().lower()
        
        if user_input == "":
            return 100
        elif user_input == "deep":
            print("\n🔥 Deep scrape selected - will scrape ALL available posts!")
            return 9999999  # Large number to get all posts
        else:
            try:
                num_posts = int(user_input)
                if num_posts > 0:
                    print(f"\n✅ Will scrape {num_posts} posts per account")
                    return num_posts
                else:
                    print("❌ Please enter a positive number")
            except ValueError:
                print("❌ Invalid input. Please enter a number or 'deep'")


# -------------------------
# Retry failed screenshot scrapes
# -------------------------
def retry_failed_scrapes(failed_accounts):
    """Retry screenshot scraping for accounts that returned N/A"""
    if not failed_accounts:
        return {}
    
    print("\n" + "="*60)
    print("🔄 RETRY FAILED SCREENSHOT SCRAPES")
    print("="*60)
    print(f"\nThe following accounts had N/A for follower count:")
    for username in failed_accounts:
        print(f"  • @{username}")
    
    while True:
        retry = input("\n🔄 Would you like to retry screenshot scraping for these accounts? (y/n): ").strip().lower()
        if retry in ["y", "yes"]:
            break
        elif retry in ["n", "no"]:
            return {}
        else:
            print("❌ Please type 'y' or 'n'.")
    
    print("\n📸 Retrying screenshot scrapes...")
    retry_results = {}
    
    for username in failed_accounts:
        print(f"\n  🔄 Retrying @{username}...")
        tokcount_followers, tokcount_likes = get_tokcount_stats(username)
        if tokcount_followers:
            retry_results[username] = (tokcount_followers, tokcount_likes)
            print(f"  ✅ Successfully retrieved: {tokcount_followers:,} followers")
        else:
            print(f"  ❌ Still N/A")
    
    return retry_results


# -------------------------
# Main scrape function
# -------------------------
def run_scrape(max_posts=None):
    import pandas as pd
    
    ensure_packages()
    
    print("\n" + "="*60)
    print("🎯 Multi-Account TikTok Analytics Tracker")
    print("="*60)
    
    # Auto-detect accounts from Excel file
    accounts_to_scrape = get_accounts_from_excel()
    
    if not accounts_to_scrape:
        print("\n❌ Could not detect accounts. Make sure the Excel file exists!")
        return
    
    # Get scrape configuration if not provided
    if max_posts is None:
        max_posts = get_scrape_config()
    
    scrape_type = "ALL posts" if max_posts == 9999999 else f"{max_posts} posts"
    print(f"\n📊 Scraping {scrape_type} per account")
    print(f"✅ Will update {len(accounts_to_scrape)} account(s)")
    
    # Load existing data
    existing_data = load_existing_excel()
    timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    all_account_data = {}
    failed_screenshot_accounts = []
    
    # Scrape each account
    for idx, username in enumerate(accounts_to_scrape, 1):
        print("\n" + "="*60)
        print(f"📱 [{idx}/{len(accounts_to_scrape)}] Processing @{username}")
        print("="*60)
        
        # Get TokCount stats
        tokcount_followers, tokcount_likes = get_tokcount_stats(username)
        
        # Track failed screenshot scrapes
        if tokcount_followers is None:
            failed_screenshot_accounts.append(username)
        
        # Get detailed post metrics
        videos_data, ytdlp_followers, ytdlp_likes = scrape_tiktok_profile(username, max_posts)
        
        # Use best available data
        followers = tokcount_followers if tokcount_followers else ytdlp_followers
        total_likes = tokcount_likes if tokcount_likes else ytdlp_likes
        
        # Create/update DataFrame
        existing_df = existing_data.get(username, pd.DataFrame())
        df = create_dataframe_for_account(videos_data, followers, total_likes, timestamp_col, existing_df)
        all_account_data[username] = df
        
        # Show summary
        show_account_summary(username, df)
    
    # Retry failed screenshot scrapes
    retry_results = retry_failed_scrapes(failed_screenshot_accounts)
    
    # Update data with retry results
    if retry_results:
        for username, (followers, total_likes) in retry_results.items():
            df = all_account_data[username]
            df.loc["followers", timestamp_col] = followers
            df.loc["total_likes", timestamp_col] = total_likes
            all_account_data[username] = df
    
    # Save to Excel
    print("\n" + "="*60)
    save_to_excel(all_account_data)
    
    print("\n✅ All accounts scraped successfully!")
    print(f"📁 Updated: '{OUTPUT_EXCEL}'")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_scrape()
