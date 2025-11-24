#!/usr/bin/env python3
"""
YouTube Shorts/Videos Analytics Tracker v1.1
- Uses YouTube Data API v3 (official, free, reliable)
- Tracks multiple YouTube channels
- Configurable scrape modes: test, custom, deep (unlimited)
- Updates Excel with separate tabs per account
- Compatible with crespomize.html analytics dashboard
- Auto-uploads to Google Drive (when configured)
- Deep scrape now goes back as far as possible with pagination
"""

import sys
import subprocess
import os
from datetime import datetime, timedelta
import time
import requests
import json
import re

OUTPUT_EXCEL = "youtube_analytics_tracker.xlsx"

# YouTube channels to track
ACCOUNTS_TO_TRACK = [
    "popdartsgame",
    "bucketgolfgame",
    "playbattlegolf",
    "FlingGolf",
    "GolfPongGames",
    "DiscGOGames"
]

# YouTube API Key
API_KEY = "AIzaSyCj1JF5t2F_vonT8UUuEqdQAeWyjz5BOPE"

# Google Drive File ID (from your link)
GDRIVE_FILE_ID = "1yRLZpJLdaB9oPZtjcwIeJx-6q8lGF2dO"

def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

def ensure_packages():
    packages_needed = []
    required = {
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

def get_channel_info(channel_name):
    """Get channel ID, statistics, and uploads playlist"""
    # Try by handle first
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        'part': 'id,snippet,statistics,contentDetails',
        'forHandle': channel_name,
        'key': API_KEY
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'items' in data and len(data['items']) > 0:
        item = data['items'][0]
        return {
            'channel_id': item['id'],
            'title': item['snippet']['title'],
            'subscribers': int(item['statistics'].get('subscriberCount', 0)),
            'total_views': int(item['statistics'].get('viewCount', 0)),
            'total_videos': int(item['statistics'].get('videoCount', 0)),
            'uploads_playlist': item['contentDetails']['relatedPlaylists']['uploads']
        }
    
    # Try search if handle doesn't work
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'part': 'snippet',
        'q': channel_name,
        'type': 'channel',
        'key': API_KEY,
        'maxResults': 1
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if 'items' in data and len(data['items']) > 0:
        channel_id = data['items'][0]['snippet']['channelId']
        
        # Get full details
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            'part': 'id,snippet,statistics,contentDetails',
            'id': channel_id,
            'key': API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'items' in data:
            item = data['items'][0]
            return {
                'channel_id': item['id'],
                'title': item['snippet']['title'],
                'subscribers': int(item['statistics'].get('subscriberCount', 0)),
                'total_views': int(item['statistics'].get('viewCount', 0)),
                'total_videos': int(item['statistics'].get('videoCount', 0)),
                'uploads_playlist': item['contentDetails']['relatedPlaylists']['uploads']
            }
    
    return None

def get_all_videos_paginated(channel_info, max_videos=None, deep_scrape=False):
    """Get videos with pagination support for deep scraping"""
    uploads_playlist = channel_info['uploads_playlist']
    all_video_ids = []
    page_token = None
    page_count = 0
    
    # For deep scrape, we'll keep going until we run out of videos
    # Otherwise, respect the max_videos limit
    target_videos = 999999 if deep_scrape else (max_videos or 30)
    
    print(f"  📹 Fetching video list{'... (unlimited deep scrape)' if deep_scrape else f' (target: {target_videos})'}...")
    
    while len(all_video_ids) < target_videos:
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            'part': 'contentDetails',
            'playlistId': uploads_playlist,
            'maxResults': 50,  # Maximum allowed per request
            'key': API_KEY
        }
        
        if page_token:
            params['pageToken'] = page_token
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'error' in data:
            print(f"  ⚠️ API Error: {data['error'].get('message', 'Unknown error')}")
            break
        
        if 'items' in data:
            video_ids = [item['contentDetails']['videoId'] for item in data['items']]
            all_video_ids.extend(video_ids)
            page_count += 1
            
            # Progress update for deep scrape
            if deep_scrape and page_count % 5 == 0:
                print(f"    Progress: {len(all_video_ids)} videos fetched...")
        
        # Check if there are more pages
        page_token = data.get('nextPageToken')
        if not page_token:
            print(f"    ✅ Reached end of channel - {len(all_video_ids)} total videos found")
            break
        
        # If not deep scraping and we have enough videos, stop
        if not deep_scrape and len(all_video_ids) >= target_videos:
            all_video_ids = all_video_ids[:target_videos]
            break
    
    return all_video_ids

def get_video_details_batch(video_ids):
    """Get full details for a batch of videos (max 50 at a time)"""
    if not video_ids:
        return []
    
    all_videos = []
    
    # Process in batches of 50 (API limit)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': ','.join(batch),
            'key': API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if 'items' in data:
            for item in data['items']:
                # Parse duration
                duration = item['contentDetails']['duration']
                match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
                if match:
                    hours = int(match.group(1) or 0)
                    minutes = int(match.group(2) or 0)
                    seconds = int(match.group(3) or 0)
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                else:
                    total_seconds = 0
                
                # Determine if it's a Short
                is_short = total_seconds <= 60
                
                stats = item['statistics']
                snippet = item['snippet']
                
                # Parse published date
                published_str = snippet['publishedAt']
                published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                
                all_videos.append({
                    'video_id': item['id'],
                    'title': snippet['title'],
                    'date': published_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'date_display': published_date.strftime('%b %d, %Y'),
                    'duration': total_seconds,
                    'is_short': is_short,
                    'views': int(stats.get('viewCount', 0)),
                    'likes': int(stats.get('likeCount', 0)),
                    'comments': int(stats.get('commentCount', 0)),
                    'favorites': int(stats.get('favoriteCount', 0))
                })
        
        # Show progress for large batches
        if len(video_ids) > 100 and (i + 50) % 100 == 0:
            print(f"    Processing details: {min(i + 50, len(video_ids))}/{len(video_ids)} videos...")
    
    return all_videos

def scrape_youtube_channel(channel_name, max_videos=30, deep_scrape=False, test_mode=False):
    """Scrape a single YouTube channel"""
    print(f"  📺 Getting channel info...")
    channel_info = get_channel_info(channel_name)
    
    if not channel_info:
        print(f"  ❌ Channel not found: {channel_name}")
        return [], None, None
    
    print(f"  ✅ Found: {channel_info['title']}")
    print(f"  👥 Subscribers: {channel_info['subscribers']:,}")
    print(f"  📊 Total channel videos: {channel_info['total_videos']:,}")
    
    # Get video IDs with pagination
    video_ids = get_all_videos_paginated(channel_info, max_videos, deep_scrape)
    
    if not video_ids:
        print(f"  ⚠️ No videos found")
        return [], channel_info['subscribers'], channel_info.get('total_views', 0)
    
    # Get detailed video info
    print(f"  📊 Getting detailed stats for {len(video_ids)} videos...")
    videos = get_video_details_batch(video_ids)
    
    # Calculate engagement rates
    for video in videos:
        if video['views'] > 0:
            engagement = ((video['likes'] + video['comments']) / video['views']) * 100
            video['engagement'] = round(engagement, 2)
        else:
            video['engagement'] = 0
    
    # Sort by date (newest first)
    videos.sort(key=lambda x: x['date'], reverse=True)
    
    # For deep scrape, show date range
    if deep_scrape and videos:
        oldest_date = datetime.strptime(videos[-1]['date'], '%Y-%m-%d %H:%M:%S')
        newest_date = datetime.strptime(videos[0]['date'], '%Y-%m-%d %H:%M:%S')
        days_span = (newest_date - oldest_date).days
        print(f"  📅 Date range: {videos[-1]['date_display']} to {videos[0]['date_display']} ({days_span} days)")
    
    if test_mode:
        print(f"\n  📋 Videos scraped:")
        for i, video in enumerate(videos[:10], 1):
            video_type = "SHORT" if video['is_short'] else "VIDEO"
            print(f"    {i}. [{video_type}] {video['title'][:50]}...")
            print(f"       Date: {video['date_display']}")
            print(f"       Views: {video['views']:,}, Likes: {video['likes']:,}")
            print(f"       Engagement: {video['engagement']}%")
    
    # Calculate total likes across all videos
    total_likes = sum(v['likes'] for v in videos)
    
    # Count shorts vs regular videos
    shorts_count = sum(1 for v in videos if v.get('is_short', False))
    print(f"  📱 Content breakdown: {shorts_count} Shorts, {len(videos) - shorts_count} regular videos")
    
    return videos, channel_info['subscribers'], total_likes

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

def create_dataframe_for_account(videos_data, subscribers, total_likes, timestamp_col, existing_df=None):
    """Create or update DataFrame for YouTube channel - matching TikTok/Instagram format"""
    import pandas as pd
    
    if existing_df is not None and not existing_df.empty:
        df = existing_df.copy()
    else:
        df = pd.DataFrame()
    
    # Add timestamp column if it doesn't exist
    if timestamp_col not in df.columns:
        df[timestamp_col] = None
    
    # Add channel-level metrics (matching TikTok format)
    df.loc["followers", timestamp_col] = subscribers  # Using 'followers' for consistency
    df.loc["total_likes", timestamp_col] = total_likes
    df.loc["posts_scraped", timestamp_col] = len(videos_data)
    
    # Add per-video metrics (using 'post_' prefix like TikTok)
    for video in videos_data:
        video_id = video['video_id']
        
        # Store each metric in the format expected by crespomize.html
        metrics = {
            'Date': video['date'],
            'Views': video['views'],
            'Likes': video['likes'],
            'Comments': video['comments'],
            'Shares': 0,  # YouTube doesn't provide share count via API
            'EngagementRate': video['engagement']
        }
        
        for metric_name, value in metrics.items():
            row_name = f"post_{video_id}_{metric_name}"
            if row_name not in df.index:
                df.loc[row_name] = None
            df.loc[row_name, timestamp_col] = value
    
    return df

def save_to_excel(all_account_data):
    """Save all account data to Excel"""
    import pandas as pd
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        for username, df in all_account_data.items():
            sheet_name = username[:31]  # Excel sheet name limit
            df.to_excel(writer, sheet_name=sheet_name)
    print(f"\n💾 Excel saved: {OUTPUT_EXCEL}")

def upload_to_google_drive():
    """Upload to Google Drive if configured"""
    print("\n" + "="*70)
    print("☁️  Uploading to Google Drive...")
    print("="*70)
    
    try:
        # Check if rclone is installed
        result = subprocess.run(['rclone', 'version'], 
            capture_output=True, 
            text=True)
        if result.returncode != 0:
            raise FileNotFoundError
        
        # Try to upload
        excel_path = os.path.abspath(OUTPUT_EXCEL)
        print(f"\n📤 Attempting to upload {OUTPUT_EXCEL}...")
        
        upload_result = subprocess.run(
            ['rclone', 'copy', excel_path, 'gdrive:', '--update', '-v'],
            capture_output=True,
            text=True
        )
        
        if upload_result.returncode == 0:
            print("✅ Successfully uploaded to Google Drive!")
            print(f"📁 File ID: {GDRIVE_FILE_ID}")
            print("🌐 View at: https://crespo.world/crespomize.html")
            print("\n📝 Update crespomize.html with:")
            print(f"   youtube: '{GDRIVE_FILE_ID}'")
            return True
        else:
            if "directory not found" in upload_result.stderr.lower() or "failed to create" in upload_result.stderr.lower():
                print("⚠️ Google Drive not configured for YouTube data yet")
                print(f"\n📁 Your Google Drive File ID: {GDRIVE_FILE_ID}")
                print("\n📝 To view in crespomize.html, update the SHEET_IDS section:")
                print(f"   youtube: '{GDRIVE_FILE_ID}'")
                return False
            else:
                print(f"⚠️ Upload issue: {upload_result.stderr}")
                return False
                
    except FileNotFoundError:
        print("⚠️ rclone not found - Google Drive upload skipped")
        print(f"\n📁 Your Google Drive File ID: {GDRIVE_FILE_ID}")
        print("\n📝 To enable automatic upload:")
        print("1. Install rclone: https://rclone.org/downloads/")
        print("2. Configure it with: rclone config")
        print("3. Run this script again")
        print("\n📝 To view in crespomize.html, update:")
        print(f"   youtube: '{GDRIVE_FILE_ID}'")
        return False
    except Exception as e:
        print(f"⚠️ Upload error: {e}")
        return False

def get_scrape_mode():
    """Get scraping mode from user"""
    print("\n" + "="*70)
    print("🎯 SELECT SCRAPE MODE")
    print("="*70)
    print("\n1. Custom number of videos (default: 30)")
    print("2. Deep scrape (ALL videos - no limit)")
    print("3. Test mode (10 videos on first channel only)")
    print()
    
    while True:
        choice = input("Enter your choice (1, 2, or 3, default=1): ").strip()
        
        if choice == '1' or choice == '':
            num_input = input("\nHow many videos per channel? (default 30): ").strip()
            try:
                num_videos = int(num_input) if num_input else 30
                if num_videos > 0:
                    return num_videos, False, False
                else:
                    print("Please enter a positive number.")
            except ValueError:
                print("Invalid input. Using default: 30")
                return 30, False, False
                
        elif choice == '2':
            confirm = input("\n⚠️ Deep scrape will fetch ALL videos from each channel. This may take a while and use significant API quota. Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                return None, True, False
                
        elif choice == '3':
            return 10, False, True
            
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

def run_scrape():
    """Main scrape function"""
    import pandas as pd
    
    ensure_packages()
    
    print("\n" + "="*70)
    print("🎬 YouTube Analytics Tracker v1.1")
    print("="*70)
    
    # Test API key
    print("\n🔑 Testing API key...")
    test_url = f"https://www.googleapis.com/youtube/v3/channels?part=id&forHandle=popdartsgame&key={API_KEY}"
    try:
        test_response = requests.get(test_url)
        if test_response.status_code == 200:
            print("✅ API key is valid!")
        else:
            print(f"❌ API key error: {test_response.json()}")
            print("\nPlease check your API key in the script")
            return
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    # Get scrape mode
    max_videos, deep_scrape, test_mode = get_scrape_mode()
    
    # Set up accounts to scrape
    if test_mode:
        print("\n🧪 TEST MODE ACTIVATED")
        print(f"   Channel: @{ACCOUNTS_TO_TRACK[0]}")
        print(f"   Videos: 10")
        print(f"   Output: Terminal + Excel file")
        accounts = [ACCOUNTS_TO_TRACK[0]]
        expected_videos = 10
    else:
        print(f"\n✅ Will scrape {len(ACCOUNTS_TO_TRACK)} channel(s):\n")
        for i, account in enumerate(ACCOUNTS_TO_TRACK, 1):
            print(f"   {i}. @{account}")
        accounts = ACCOUNTS_TO_TRACK
        if deep_scrape:
            print("\n🔍 Mode: DEEP SCRAPE (ALL videos, no limit)")
            expected_videos = None
        else:
            print(f"\n📊 Mode: {max_videos} videos per channel")
            expected_videos = max_videos
    
    input("\n▶️ Press ENTER to start scraping...")
    
    # Load existing data
    existing_data = load_existing_excel()
    timestamp_col = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_account_data = {}
    scrape_results = {}
    total_api_calls = 0
    
    # Scrape each channel
    for idx, channel_name in enumerate(accounts, 1):
        print("\n" + "="*70)
        if test_mode:
            print(f"🧪 TEST SCRAPE: @{channel_name}")
        else:
            print(f"📺 [{idx}/{len(accounts)}] Processing @{channel_name}")
        print("="*70)
        
        try:
            videos_data, subscribers, total_likes = scrape_youtube_channel(
                channel_name, 
                max_videos=expected_videos, 
                deep_scrape=deep_scrape,
                test_mode=test_mode
            )
            
            # Estimate API calls (rough)
            api_calls = 1 + (len(videos_data) // 50) + 1  # channel info + video batches
            if deep_scrape:
                api_calls += (len(videos_data) // 50)  # pagination calls
            total_api_calls += api_calls
            
            scrape_results[channel_name] = {
                'videos_count': len(videos_data),
                'subscribers': subscribers,
                'total_likes': total_likes
            }
            
            if test_mode:
                print("\n" + "="*70)
                print("✅ TEST COMPLETE!")
                print("="*70)
                print(f"\n📊 Summary:")
                print(f"   Channel: @{channel_name}")
                print(f"   Subscribers: {subscribers:,}")
                print(f"   Videos scraped: {len(videos_data)}")
                print(f"   Total likes: {total_likes:,}")
                
                # Count Shorts vs regular videos
                shorts_count = sum(1 for v in videos_data if v.get('is_short', False))
                print(f"   Shorts: {shorts_count}, Regular videos: {len(videos_data) - shorts_count}")
                
                if videos_data:
                    avg_views = sum(v['views'] for v in videos_data) / len(videos_data)
                    avg_engagement = sum(v['engagement'] for v in videos_data) / len(videos_data)
                    print(f"   Average views: {avg_views:,.0f}")
                    print(f"   Average engagement: {avg_engagement:.2f}%")
                
                print(f"\n💡 Data will be saved to Excel in the same format as TikTok/Instagram")
                print("   Compatible with crespomize.html analytics dashboard")
            
            # Create/update DataFrame
            existing_df = existing_data.get(channel_name, pd.DataFrame())
            df = create_dataframe_for_account(
                videos_data, subscribers, total_likes, timestamp_col, existing_df
            )
            all_account_data[channel_name] = df
            
            if not test_mode:
                print(f"\n  ✅ @{channel_name} complete!")
                print(f"  👥 Subscribers: {subscribers:,}")
                print(f"  🎬 Videos: {len(videos_data)}")
                print(f"  👍 Total likes: {total_likes:,}")
                
        except Exception as e:
            print(f"\n  ❌ Error with @{channel_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Save to Excel
    if all_account_data:
        save_to_excel(all_account_data)
        
        # Try to upload to Google Drive
        upload_success = upload_to_google_drive()
        
        if not upload_success:
            print("\n" + "="*70)
            print("📁 LOCAL FILE SAVED SUCCESSFULLY")
            print("="*70)
            print(f"\n✅ Excel file saved: {OUTPUT_EXCEL}")
            print(f"\n📁 Google Drive File ID: {GDRIVE_FILE_ID}")
            print("\n📝 To view in analytics dashboard:")
            print("1. Upload this file to your Google Drive (replacing the existing one)")
            print("2. Update crespomize.html with:")
            print(f"   youtube: '{GDRIVE_FILE_ID}'")
            print("3. Ensure file has public read permissions")
    
    # Final summary
    print("\n" + "="*70)
    print("✅ SCRAPING COMPLETE!")
    print("="*70)
    
    total_videos = 0
    for channel, result in scrape_results.items():
        print(f"\n@{channel}:")
        print(f"  Videos: {result['videos_count']}")
        print(f"  Subscribers: {result['subscribers']:,}")
        print(f"  Total Likes: {result['total_likes']:,}")
        total_videos += result['videos_count']
    
    print(f"\n📊 Totals:")
    print(f"  Channels scraped: {len(scrape_results)}")
    print(f"  Total videos: {total_videos}")
    print(f"  Estimated API calls: ~{total_api_calls * 100} units")
    print(f"  Daily quota remaining: ~{10000 - (total_api_calls * 100)} units")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    run_scrape()
