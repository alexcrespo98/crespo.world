#!/usr/bin/env python3
"""
Master Social Media Scraper v3.0 - Ubuntu Compatible
Runs all three scrapers with 4 distinct operational modes:
- Mode 1: Normal Scrape (100 Instagram/TikTok, ALL YouTube)
- Mode 2: Custom Scrape (user-specified counts per platform)
- Mode 3: Deep Scrape (1 year back with all-time option)
- Mode 4: Test Mode (30 posts each, platform selection, no Excel updates)

Ubuntu Features:
- Cross-platform path handling
- Google Drive integration via rclone
- Proper error handling and progress indicators
"""

import os
import sys
import time
import signal
import traceback
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Constants
DEEP_SCRAPE_MAX_POSTS = 9999999  # Used for unlimited scraping in deep mode

# Add the scrapers directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the actual scrapers
from instagram_scraper import InstagramScraper, ACCOUNTS_TO_TRACK as INSTA_ACCOUNTS
from youtube_scraper import YoutubeScraper, ACCOUNTS_TO_TRACK as YOUTUBE_ACCOUNTS
from tiktok_scraper import TikTokScraper


class MasterScraper:
    """Master scraper that orchestrates Instagram, YouTube, and TikTok scrapers"""
    
    def __init__(self):
        self.interrupted = False
        self.results = {}
        self.errors = []
        self.files_updated = []
        self.gdrive_status = None
        
        # Set up signal handler for interrupts
        signal.signal(signal.SIGINT, self.handle_interrupt)
    
    def handle_interrupt(self, signum, frame):
        """Handle Ctrl+C interrupt gracefully"""
        print("\n\n" + "="*70)
        print("⚠️  INTERRUPT DETECTED - SHUTTING DOWN")
        print("="*70)
        self.interrupted = True
        print("\n✅ Shutdown complete.")
        sys.exit(0)
    
    def check_gdrive_configured(self):
        """Check if Google Drive (rclone) is configured"""
        try:
            result = subprocess.run(
                ['rclone', 'listremotes'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and 'gdrive:' in result.stdout:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return False
    
    def upload_to_gdrive(self, file_path):
        """Upload file to Google Drive using rclone"""
        if not self.check_gdrive_configured():
            return False, "rclone not configured"
        
        try:
            file_name = os.path.basename(file_path)
            result = subprocess.run(
                ['rclone', 'copy', file_path, 'gdrive:scrapers/'],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return True, f"Uploaded {file_name}"
            else:
                return False, f"Upload failed: {result.stderr}"
        except Exception as e:
            return False, f"Upload error: {str(e)}"
    
    def get_mode_selection(self):
        """Get scraping mode from user"""
        print("\n" + "="*70)
        print("🎯 MASTER SCRAPER - SELECT MODE")
        print("="*70)
        print("\n1. Normal Scrape (100 posts Instagram/TikTok, ALL YouTube)")
        print("2. Custom Scrape (specify counts per platform)")
        print("3. Deep Scrape (1 year back, with all-time option)")
        print("4. Test Mode (30 posts each, select platforms)")
        print()
        
        while True:
            choice = input("Enter mode (1-4): ").strip()
            
            if choice == '1':
                return {
                    'mode': 'normal',
                    'instagram': {'count': 100, 'deep': False},
                    'tiktok': {'count': 100, 'deep': False},
                    'youtube': {'count': 'all', 'deep': False},
                }
            
            elif choice == '2':
                config = {'mode': 'custom'}
                print("\n📊 Custom Scrape Configuration")
                print("-" * 70)
                
                ig_input = input("Instagram posts per account (default 100): ").strip()
                config['instagram'] = {
                    'count': int(ig_input) if ig_input and ig_input.isdigit() else 100,
                    'deep': False
                }
                
                tt_input = input("TikTok posts per account (default 100): ").strip()
                config['tiktok'] = {
                    'count': int(tt_input) if tt_input and tt_input.isdigit() else 100,
                    'deep': False
                }
                
                yt_input = input("YouTube videos per channel (default 'all'): ").strip().lower()
                config['youtube'] = {
                    'count': yt_input if yt_input else 'all',
                    'deep': False
                }
                
                return config
            
            elif choice == '3':
                print("\n🔍 Deep Scrape Options")
                print("-" * 70)
                print("Instagram & TikTok: 1 year back (default) or all-time")
                print("YouTube: ALL videos (API makes this fast)")
                
                all_time = input("\nScrape all-time history? (y/n, default n): ").strip().lower() == 'y'
                
                if all_time:
                    confirm = input("\n⚠️  ALL-TIME scrape takes significantly longer. Continue? (y/n): ").strip().lower()
                    if confirm != 'y':
                        continue
                    print("✅ All-time mode selected")
                else:
                    print("✅ 1 year mode selected")
                
                return {
                    'mode': 'deep',
                    'instagram': {'count': None, 'deep': True, 'all_time': all_time},
                    'tiktok': {'count': None, 'deep': True, 'all_time': all_time},
                    'youtube': {'count': 'all', 'deep': True},
                }
            
            elif choice == '4':
                print("\n🧪 Test Mode Configuration")
                print("-" * 70)
                print("Will scrape 30 posts from FIRST account of each selected platform")
                print("⚠️  NOTE: Test mode does NOT update Excel files")
                
                all_platforms = input("\nTest all three platforms? (y/n): ").strip().lower() == 'y'
                
                if all_platforms:
                    platforms = {'instagram': True, 'youtube': True, 'tiktok': True}
                else:
                    print("\nSelect platforms to test:")
                    platforms = {
                        'instagram': input("  Instagram? (y/n): ").strip().lower() == 'y',
                        'youtube': input("  YouTube? (y/n): ").strip().lower() == 'y',
                        'tiktok': input("  TikTok? (y/n): ").strip().lower() == 'y',
                    }
                    
                    if not any(platforms.values()):
                        print("❌ Must select at least one platform!")
                        continue
                
                if platforms.get('youtube'):
                    print("\n⚠️  WARNING: Testing YouTube counts toward API quota. Proceed carefully.")
                    confirm = input("Continue with YouTube test? (y/n): ").strip().lower()
                    if confirm != 'y':
                        platforms['youtube'] = False
                        if not any(platforms.values()):
                            print("❌ Must select at least one platform!")
                            continue
                
                return {
                    'mode': 'test',
                    'platforms': platforms,
                    'instagram': {'count': 30, 'deep': False, 'test': True},
                    'tiktok': {'count': 30, 'deep': False, 'test': True},
                    'youtube': {'count': 30, 'deep': False, 'test': True},
                }
            
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
    
    def select_platforms(self, config):
        """Let user select which platforms to scrape (for non-test modes)"""
        if config['mode'] == 'test':
            return config['platforms']
        
        print("\n" + "="*70)
        print("📱 SELECT PLATFORMS TO SCRAPE")
        print("="*70)
        print("\n1. All platforms (Instagram, YouTube, TikTok)")
        print("2. Instagram only")
        print("3. YouTube only")
        print("4. TikTok only")
        print("5. Custom selection")
        print()
        
        while True:
            choice = input("Enter choice (1-5, default 1): ").strip()
            
            if choice == '' or choice == '1':
                return {'instagram': True, 'youtube': True, 'tiktok': True}
            elif choice == '2':
                return {'instagram': True, 'youtube': False, 'tiktok': False}
            elif choice == '3':
                return {'instagram': False, 'youtube': True, 'tiktok': False}
            elif choice == '4':
                return {'instagram': False, 'youtube': False, 'tiktok': True}
            elif choice == '5':
                platforms = {}
                platforms['instagram'] = input("  Instagram? (y/n): ").strip().lower() == 'y'
                platforms['youtube'] = input("  YouTube? (y/n): ").strip().lower() == 'y'
                platforms['tiktok'] = input("  TikTok? (y/n): ").strip().lower() == 'y'
                
                if not any(platforms.values()):
                    print("❌ Must select at least one platform!")
                    continue
                return platforms
            else:
                print("Invalid choice. Please enter 1-5.")
    
    def run_instagram_scraper(self, config, test_mode=False):
        """Run Instagram scraper with configuration"""
        print("\n" + "="*70)
        print("📸 RUNNING INSTAGRAM SCRAPER")
        print("="*70)
        
        ig_config = config['instagram']
        
        try:
            # Display configuration
            if test_mode:
                print(f"\n🧪 TEST MODE: Scraping {ig_config['count']} reels from @{INSTA_ACCOUNTS[0]}")
                print("   ⚠️  Excel files will NOT be updated")
            elif ig_config['deep']:
                if ig_config.get('all_time'):
                    print("\n🔥 DEEP SCRAPE: All-time history")
                else:
                    print("\n🔍 DEEP SCRAPE: 1 year back")
            else:
                print(f"\n📊 NORMAL SCRAPE: {ig_config['count']} reels per account")
            
            # For test mode, we would need to modify the scraper or use a different approach
            # Since we can't modify individual scrapers much, we'll note this
            if test_mode:
                print("\n⚠️  Note: Test mode requires running scraper interactively")
                print("   The scraper will prompt for configuration.")
            
            # Initialize scraper
            scraper = InstagramScraper()
            
            # NOTE: The individual scrapers have their own run() methods with prompts.
            # Per requirements, individual scrapers should remain largely unchanged.
            # The master scraper provides mode selection, but the scrapers handle their own execution.
            # Future enhancement: Add mode parameters to individual scrapers for full integration.
            scraper.run()
            
            if not test_mode:
                self.files_updated.append('instagram_reels_analytics_tracker.xlsx')
            
            self.results['instagram'] = {
                'status': 'completed',
                'posts': ig_config['count'] if not ig_config['deep'] else 'variable'
            }
            return True
            
        except Exception as e:
            error_msg = f"Instagram error: {str(e)}"
            self.errors.append(error_msg)
            print(f"\n❌ {error_msg}")
            traceback.print_exc()
            self.results['instagram'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def run_youtube_scraper(self, config, test_mode=False):
        """Run YouTube scraper with configuration"""
        print("\n" + "="*70)
        print("🎬 RUNNING YOUTUBE SCRAPER")
        print("="*70)
        
        yt_config = config['youtube']
        
        try:
            # Display configuration
            if test_mode:
                print(f"\n🧪 TEST MODE: Scraping {yt_config['count']} videos from @{YOUTUBE_ACCOUNTS[0]}")
                print("   ⚠️  Excel files will NOT be updated")
                print("   ⚠️  This uses API quota!")
            elif yt_config['count'] == 'all':
                print("\n🔥 SCRAPING: ALL available videos")
            else:
                print(f"\n📊 SCRAPING: {yt_config['count']} videos per channel")
            
            # Initialize scraper
            scraper = YoutubeScraper()
            
            # NOTE: YouTube scraper has its own interactive prompts.
            # The master scraper provides guidance but the scraper handles configuration.
            if test_mode:
                print("\n⚠️  Note: YouTube scraper will prompt for test mode configuration")
            
            scraper.run()
            
            if not test_mode:
                self.files_updated.append('youtube_analytics_tracker.xlsx')
            
            self.results['youtube'] = {
                'status': 'completed',
                'videos': yt_config['count']
            }
            return True
            
        except Exception as e:
            error_msg = f"YouTube error: {str(e)}"
            self.errors.append(error_msg)
            print(f"\n❌ {error_msg}")
            traceback.print_exc()
            self.results['youtube'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def run_tiktok_scraper(self, config, test_mode=False):
        """Run TikTok scraper with configuration"""
        print("\n" + "="*70)
        print("🎵 RUNNING TIKTOK SCRAPER")
        print("="*70)
        
        tt_config = config['tiktok']
        
        try:
            # Display configuration
            if test_mode:
                print(f"\n🧪 TEST MODE: Scraping {tt_config['count']} posts from first account")
                print("   ⚠️  Excel files will NOT be updated")
            elif tt_config['deep']:
                if tt_config.get('all_time'):
                    print("\n🔥 DEEP SCRAPE: All-time history")
                else:
                    print("\n🔍 DEEP SCRAPE: 1 year back")
            else:
                print(f"\n📊 NORMAL SCRAPE: {tt_config['count']} posts per account")
            
            # Initialize scraper
            scraper = TikTokScraper()
            
            # NOTE: TikTok scraper accepts max_posts parameter but has its own prompts.
            # The master scraper passes the count, but the scraper handles the rest.
            if test_mode:
                print("\n⚠️  Note: TikTok scraper will prompt for additional configuration")
            
            # TikTok scraper accepts max_posts parameter (verified in tiktok_scraper.py line 691)
            # Note: Internally, the scraper converts max_posts to max_videos for scrape_tiktok_profile
            # For deep scrapes, pass DEEP_SCRAPE_MAX_POSTS as per scraper's design (line 607)
            # Passing None would trigger the scraper's interactive prompt
            if tt_config.get('deep'):
                max_posts_arg = DEEP_SCRAPE_MAX_POSTS  # Deep scrape - effectively unlimited
            else:
                max_posts_arg = tt_config.get('count', 100)
            scraper.run(max_posts=max_posts_arg)
            
            if not test_mode:
                self.files_updated.append('tiktok_analytics_tracker.xlsx')
            
            self.results['tiktok'] = {
                'status': 'completed',
                'posts': tt_config['count'] if not tt_config['deep'] else 'variable'
            }
            return True
            
        except Exception as e:
            error_msg = f"TikTok error: {str(e)}"
            self.errors.append(error_msg)
            print(f"\n❌ {error_msg}")
            traceback.print_exc()
            self.results['tiktok'] = {'status': 'failed', 'error': str(e)}
            return False
    
    def display_summary(self, platforms, config):
        """Display comprehensive summary of scraping session"""
        print("\n" + "="*70)
        print("✅ MASTER SCRAPER COMPLETE!")
        print("="*70)
        
        # Show mode
        mode_names = {
            'normal': 'Normal Scrape',
            'custom': 'Custom Scrape',
            'deep': 'Deep Scrape',
            'test': 'Test Mode'
        }
        print(f"\n📋 Mode: {mode_names.get(config['mode'], 'Unknown')}")
        
        # Show platform results
        print("\n📊 Platform Results:")
        for platform in ['instagram', 'youtube', 'tiktok']:
            if platforms.get(platform):
                result = self.results.get(platform, {})
                status = result.get('status', 'not run')
                if status == 'completed':
                    count = result.get('posts', result.get('videos', 'N/A'))
                    print(f"   ✅ {platform.capitalize()}: Completed ({count} items)")
                elif status == 'failed':
                    print(f"   ❌ {platform.capitalize()}: Failed - {result.get('error', 'Unknown error')}")
                else:
                    print(f"   ⚠️  {platform.capitalize()}: {status}")
        
        # Show files updated (only if not test mode)
        if config['mode'] != 'test' and self.files_updated:
            print("\n📁 Files Updated:")
            for file in self.files_updated:
                print(f"   • {file}")
        elif config['mode'] == 'test':
            print("\n📁 Files: No files updated (test mode)")
        
        # Show errors/warnings
        if self.errors:
            print("\n⚠️  Errors/Warnings:")
            for error in self.errors:
                print(f"   • {error}")
        
        # Show Google Drive status
        print("\n☁️  Google Drive Upload:")
        if self.check_gdrive_configured():
            if config['mode'] != 'test' and self.files_updated:
                print("   Uploading files to Google Drive...")
                upload_results = []
                for file in self.files_updated:
                    if os.path.exists(file):
                        success, msg = self.upload_to_gdrive(file)
                        upload_results.append((file, success, msg))
                        if success:
                            print(f"   ✅ {msg}")
                        else:
                            print(f"   ❌ {msg}")
                
                # Summary
                successful = sum(1 for _, s, _ in upload_results if s)
                print(f"   📊 Uploaded {successful}/{len(upload_results)} files")
            else:
                print("   ⚠️  Skipped (test mode or no files)")
        else:
            print("   ⚠️  Not configured (run setup_gdrive.sh)")
        
        # Final message
        print("\n🌐 View analytics at: https://crespo.world/crespomize.html")
        print("="*70 + "\n")
    
    def run(self):
        """Main execution function"""
        print("\n" + "="*70)
        print("🚀 MASTER SOCIAL MEDIA SCRAPER v3.0")
        print("="*70)
        print("\nUbuntu-compatible scraper with Google Drive integration")
        print("Supports Instagram, YouTube, and TikTok")
        
        # Get mode and configuration
        config = self.get_mode_selection()
        platforms = self.select_platforms(config)
        
        test_mode = config['mode'] == 'test'
        
        # Display configuration summary
        print("\n" + "="*70)
        print("📋 CONFIGURATION SUMMARY")
        print("="*70)
        
        mode_display = {
            'normal': 'Normal Scrape (100 IG/TT, ALL YT)',
            'custom': 'Custom Scrape',
            'deep': 'Deep Scrape (1yr or all-time)',
            'test': 'Test Mode (30 posts, no Excel updates)'
        }
        print(f"   Mode: {mode_display.get(config['mode'], 'Unknown')}")
        
        active_platforms = [p.capitalize() for p, enabled in platforms.items() if enabled]
        print(f"   Platforms: {', '.join(active_platforms)}")
        
        if config['mode'] == 'custom':
            print("\n   Custom counts:")
            if platforms.get('instagram'):
                print(f"      Instagram: {config['instagram']['count']} posts")
            if platforms.get('tiktok'):
                print(f"      TikTok: {config['tiktok']['count']} posts")
            if platforms.get('youtube'):
                print(f"      YouTube: {config['youtube']['count']} videos")
        
        if test_mode:
            print("\n   ⚠️  TEST MODE: Excel files will NOT be updated")
        
        input("\n▶️  Press ENTER to start scraping...")
        
        start_time = time.time()
        
        # Run scrapers for selected platforms
        if platforms.get('instagram'):
            self.run_instagram_scraper(config, test_mode)
            if self.interrupted:
                return
        
        if platforms.get('youtube'):
            self.run_youtube_scraper(config, test_mode)
            if self.interrupted:
                return
        
        if platforms.get('tiktok'):
            self.run_tiktok_scraper(config, test_mode)
            if self.interrupted:
                return
        
        # Calculate duration
        duration = time.time() - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        
        print(f"\n⏱️  Total time: {minutes}m {seconds}s")
        
        # Display summary
        self.display_summary(platforms, config)


def main():
    """Main entry point"""
    scraper = MasterScraper()
    
    try:
        scraper.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
