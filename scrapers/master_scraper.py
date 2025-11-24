import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
from pathlib import Path

# Import your existing scrapers
from instagram_scraper import InstagramScraper
from youtube_scraper import YoutubeScraper
from tiktok_scraper import TikTokScraper
from google_drive_uploader import GoogleDriveUploader

class MasterScraper:
    def __init__(self, mode='custom', days_back=30, test_account='popdarts'):
        """
        Initialize the master scraper
        
        Args:
            mode: 'custom' (default 30 days), 'deep' (all posts), or 'test' (30 posts from test account)
            days_back: Number of days to scrape back (only for custom mode)
            test_account: Account to use for test mode
        """
        self.mode = mode
        self.days_back = days_back
        self.test_account = test_account
        self.failed_posts = {'instagram': [], 'youtube': [], 'tiktok': []}
        self.total_posts = {'instagram': 0, 'youtube': 0, 'tiktok': 0}
        
        # Initialize scrapers
        self.instagram_scraper = InstagramScraper()
        self.youtube_scraper = YoutubeScraper()
        self.tiktok_scraper = TikTokScraper()
        self.drive_uploader = GoogleDriveUploader()
        
        # Set date limits based on mode
        if mode == 'custom':
            self.start_date = datetime.now() - timedelta(days=days_back)
        elif mode == 'deep':
            self.start_date = datetime(2000, 1, 1)  # Effectively no limit
        else:  # test mode
            self.start_date = None
            
    def load_social_accounts(self) -> Dict[str, List[str]]:
        """Load social media accounts from moonmediasocials file"""
        accounts = {
            'instagram': [],
            'youtube': [],
            'tiktok': []
        }
        
        try:
            # Adjust path based on your file structure
            with open('moonmediasocials.json', 'r') as f:
                data = json.load(f)
                
            for entry in data:
                if 'instagram' in entry and entry['instagram']:
                    accounts['instagram'].append(entry['instagram'])
                if 'youtube' in entry and entry['youtube']:
                    accounts['youtube'].append(entry['youtube'])
                if 'tiktok' in entry and entry['tiktok']:
                    accounts['tiktok'].append(entry['tiktok'])
                    
            return accounts
            
        except FileNotFoundError:
            print("Error: moonmediasocials.json not found")
            return accounts
        except Exception as e:
            print(f"Error loading social accounts: {e}")
            return accounts
    
    def scrape_instagram(self, accounts: List[str]) -> pd.DataFrame:
        """Scrape Instagram accounts based on mode"""
        all_data = []
        
        for account in accounts:
            if self.mode == 'test':
                account = self.test_account
                
            print(f"\nScraping Instagram: @{account}")
            
            try:
                if self.mode == 'test':
                    # Test mode: scrape 30 posts
                    posts = self.instagram_scraper.scrape_recent_posts(account, limit=30)
                else:
                    # Custom or deep mode: scrape by date
                    posts = self.instagram_scraper.scrape_by_date(
                        account, 
                        start_date=self.start_date
                    )
                
                for post in posts:
                    try:
                        # Extract post data with error handling
                        post_data = self.process_instagram_post(post, account)
                        all_data.append(post_data)
                        self.total_posts['instagram'] += 1
                    except Exception as e:
                        self.failed_posts['instagram'].append({
                            'account': account,
                            'post_id': post.get('id', 'unknown'),
                            'error': str(e)
                        })
                        
            except Exception as e:
                print(f"Error scraping Instagram @{account}: {e}")
                
            if self.mode == 'test':
                break  # Only scrape test account once
                
        return pd.DataFrame(all_data)
    
    def scrape_youtube(self, channels: List[str]) -> pd.DataFrame:
        """Scrape YouTube channels based on mode"""
        all_data = []
        
        for channel in channels:
            if self.mode == 'test':
                channel = self.test_account
                
            print(f"\nScraping YouTube: {channel}")
            
            try:
                if self.mode == 'test':
                    # Test mode: scrape 30 videos
                    videos = self.youtube_scraper.scrape_recent_videos(channel, limit=30)
                else:
                    # Custom or deep mode: scrape by date
                    videos = self.youtube_scraper.scrape_by_date(
                        channel,
                        start_date=self.start_date
                    )
                
                for video in videos:
                    try:
                        video_data = self.process_youtube_video(video, channel)
                        all_data.append(video_data)
                        self.total_posts['youtube'] += 1
                    except Exception as e:
                        self.failed_posts['youtube'].append({
                            'channel': channel,
                            'video_id': video.get('id', 'unknown'),
                            'error': str(e)
                        })
                        
            except Exception as e:
                print(f"Error scraping YouTube {channel}: {e}")
                
            if self.mode == 'test':
                break
                
        return pd.DataFrame(all_data)
    
    def scrape_tiktok(self, accounts: List[str]) -> pd.DataFrame:
        """Scrape TikTok accounts based on mode"""
        all_data = []
        
        for account in accounts:
            if self.mode == 'test':
                account = self.test_account
                
            print(f"\nScraping TikTok: @{account}")
            
            try:
                if self.mode == 'test':
                    # Test mode: scrape 30 videos
                    videos = self.tiktok_scraper.scrape_recent_videos(account, limit=30)
                else:
                    # Custom or deep mode: scrape by date
                    videos = self.tiktok_scraper.scrape_by_date(
                        account,
                        start_date=self.start_date
                    )
                
                for video in videos:
                    try:
                        video_data = self.process_tiktok_video(video, account)
                        all_data.append(video_data)
                        self.total_posts['tiktok'] += 1
                    except Exception as e:
                        self.failed_posts['tiktok'].append({
                            'account': account,
                            'video_id': video.get('id', 'unknown'),
                            'error': str(e)
                        })
                        
            except Exception as e:
                print(f"Error scraping TikTok @{account}: {e}")
                
            if self.mode == 'test':
                break
                
        return pd.DataFrame(all_data)
    
    def process_instagram_post(self, post: Dict, account: str) -> Dict:
        """Process Instagram post data"""
        return {
            'platform': 'instagram',
            'account': account,
            'post_id': post.get('id', 'N/A'),
            'url': post.get('url', 'N/A'),
            'caption': post.get('caption', 'N/A'),
            'likes': post.get('like_count', 0),
            'comments': post.get('comment_count', 0),
            'timestamp': post.get('timestamp', 'N/A'),
            'media_type': post.get('media_type', 'N/A'),
            'scraped_at': datetime.now().isoformat()
        }
    
    def process_youtube_video(self, video: Dict, channel: str) -> Dict:
        """Process YouTube video data"""
        return {
            'platform': 'youtube',
            'channel': channel,
            'video_id': video.get('id', 'N/A'),
            'url': f"https://youtube.com/watch?v={video.get('id', '')}",
            'title': video.get('title', 'N/A'),
            'description': video.get('description', 'N/A')[:500],  # Truncate long descriptions
            'views': video.get('view_count', 0),
            'likes': video.get('like_count', 0),
            'comments': video.get('comment_count', 0),
            'duration': video.get('duration', 'N/A'),
            'published_at': video.get('published_at', 'N/A'),
            'scraped_at': datetime.now().isoformat()
        }
    
    def process_tiktok_video(self, video: Dict, account: str) -> Dict:
        """Process TikTok video data"""
        return {
            'platform': 'tiktok',
            'account': account,
            'video_id': video.get('id', 'N/A'),
            'url': video.get('url', 'N/A'),
            'description': video.get('description', 'N/A'),
            'views': video.get('play_count', 0),
            'likes': video.get('digg_count', 0),
            'comments': video.get('comment_count', 0),
            'shares': video.get('share_count', 0),
            'created_at': video.get('create_time', 'N/A'),
            'scraped_at': datetime.now().isoformat()
        }
    
    def save_results(self, data: pd.DataFrame, platform: str) -> str:
        """Save scraped data to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if self.mode == 'test':
            # For test mode, just display in terminal
            print(f"\n{'='*50}")
            print(f"TEST MODE RESULTS - {platform.upper()}")
            print(f"{'='*50}")
            print(data.to_string())
            return None
        
        # Create output directory
        output_dir = Path('scraped_data')
        output_dir.mkdir(exist_ok=True)
        
        # Generate filename
        mode_suffix = f"{self.mode}_{self.days_back}days" if self.mode == 'custom' else self.mode
        filename = f"{platform}_{mode_suffix}_{timestamp}.csv"
        filepath = output_dir / filename
        
        # Save to CSV
        data.to_csv(filepath, index=False)
        print(f"Saved {len(data)} {platform} posts to {filepath}")
        
        return str(filepath)
    
    def upload_to_drive(self, filepath: str, platform: str):
        """Upload file to Google Drive"""
        try:
            # Define folder IDs for each platform (you'll need to set these)
            folder_ids = {
                'instagram': 'YOUR_INSTAGRAM_FOLDER_ID',
                'youtube': 'YOUR_YOUTUBE_FOLDER_ID',
                'tiktok': 'YOUR_TIKTOK_FOLDER_ID'
            }
            
            folder_id = folder_ids.get(platform)
            if folder_id:
                file_id = self.drive_uploader.upload_file(filepath, folder_id)
                print(f"Uploaded to Google Drive: {file_id}")
            else:
                print(f"No Google Drive folder configured for {platform}")
                
        except Exception as e:
            print(f"Error uploading to Google Drive: {e}")
    
    def calculate_failure_rate(self) -> Dict[str, float]:
        """Calculate failure rate for each platform"""
        failure_rates = {}
        
        for platform in ['instagram', 'youtube', 'tiktok']:
            total = self.total_posts[platform]
            failed = len(self.failed_posts[platform])
            
            if total > 0:
                failure_rates[platform] = (failed / (total + failed)) * 100
            else:
                failure_rates[platform] = 0
                
        return failure_rates
    
    def display_error_summary(self):
        """Display summary of errors and failure rates"""
        print(f"\n{'='*60}")
        print("SCRAPING SUMMARY")
        print(f"{'='*60}")
        
        failure_rates = self.calculate_failure_rate()
        
        for platform in ['instagram', 'youtube', 'tiktok']:
            total = self.total_posts[platform]
            failed = len(self.failed_posts[platform])
            rate = failure_rates[platform]
            
            print(f"\n{platform.upper()}:")
            print(f"  Successfully scraped: {total}")
            print(f"  Failed: {failed}")
            print(f"  Failure rate: {rate:.1f}%")
            
            if failed > 0 and failed <= 5:
                print(f"  Failed posts:")
                for fail in self.failed_posts[platform][:5]:
                    print(f"    - {fail['account']}: {fail['error'][:50]}")
    
    def retry_failed_posts(self) -> bool:
        """Ask user if they want to retry failed posts"""
        total_failed = sum(len(posts) for posts in self.failed_posts.values())
        
        if total_failed == 0:
            return False
            
        print(f"\n{total_failed} total posts failed to scrape.")
        response = input("Would you like to retry failed posts? (y/n): ").lower()
        
        if response == 'y':
            return True
        return False
    
    def rescrape_failed(self):
        """Attempt to rescrape failed posts"""
        print("\nRetrying failed posts...")
        
        # Instagram retries
        if self.failed_posts['instagram']:
            print(f"\nRetrying {len(self.failed_posts['instagram'])} Instagram posts...")
            for fail in self.failed_posts['instagram']:
                try:
                    # Implement retry logic here
                    # This would need to be customized based on your scraper implementation
                    pass
                except Exception as e:
                    print(f"  Retry failed for {fail['account']}: {e}")
        
        # Similar for YouTube and TikTok
        # ...
    
    def run(self):
        """Main execution function"""
        print(f"\n{'='*60}")
        print(f"MASTER SCRAPER - {self.mode.upper()} MODE")
        if self.mode == 'custom':
            print(f"Scraping posts from last {self.days_back} days")
        elif self.mode == 'deep':
            print("Scraping ALL historical posts")
        else:
            print(f"Test mode: Scraping 30 posts from @{self.test_account}")
        print(f"{'='*60}")
        
        # Load social accounts
        print("\nLoading social media accounts...")
        accounts = self.load_social_accounts()
        
        print(f"Found:")
        print(f"  Instagram: {len(accounts['instagram'])} accounts")
        print(f"  YouTube: {len(accounts['youtube'])} channels")
        print(f"  TikTok: {len(accounts['tiktok'])} accounts")
        
        # Scrape each platform
        results = {}
        
        # Instagram
        if accounts['instagram'] or self.mode == 'test':
            print(f"\n{'='*40}\nSCRAPING INSTAGRAM\n{'='*40}")
            instagram_data = self.scrape_instagram(accounts['instagram'])
            if not instagram_data.empty:
                filepath = self.save_results(instagram_data, 'instagram')
                if filepath and self.mode != 'test':
                    self.upload_to_drive(filepath, 'instagram')
                results['instagram'] = instagram_data
        
        # YouTube
        if accounts['youtube'] or self.mode == 'test':
            print(f"\n{'='*40}\nSCRAPING YOUTUBE\n{'='*40}")
            youtube_data = self.scrape_youtube(accounts['youtube'])
            if not youtube_data.empty:
                filepath = self.save_results(youtube_data, 'youtube')
                if filepath and self.mode != 'test':
                    self.upload_to_drive(filepath, 'youtube')
                results['youtube'] = youtube_data
        
        # TikTok
        if accounts['tiktok'] or self.mode == 'test':
            print(f"\n{'='*40}\nSCRAPING TIKTOK\n{'='*40}")
            tiktok_data = self.scrape_tiktok(accounts['tiktok'])
            if not tiktok_data.empty:
                filepath = self.save_results(tiktok_data, 'tiktok')
                if filepath and self.mode != 'test':
                    self.upload_to_drive(filepath, 'tiktok')
                results['tiktok'] = tiktok_data
        
        # Display error summary
        self.display_error_summary()
        
        # Ask about retrying failed posts
        if self.retry_failed_posts():
            self.rescrape_failed()
            # Display updated summary
            self.display_error_summary()
        
        print(f"\n{'='*60}")
        print("SCRAPING COMPLETE!")
        print(f"{'='*60}\n")
        
        return results


def main():
    """Main entry point with command line arguments"""
    parser = argparse.ArgumentParser(description='Master Social Media Scraper')
    parser.add_argument(
        '--mode',
        choices=['custom', 'deep', 'test'],
        default='custom',
        help='Scraping mode: custom (default 30 days), deep (all posts), or test'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to scrape back (only for custom mode)'
    )
    parser.add_argument(
        '--test-account',
        default='popdarts',
        help='Account to use for test mode'
    )
    
    args = parser.parse_args()
    
    # Create and run scraper
    scraper = MasterScraper(
        mode=args.mode,
        days_back=args.days,
        test_account=args.test_account
    )
    
    try:
        results = scraper.run()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
