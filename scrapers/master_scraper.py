#!/usr/bin/env python3
"""
Master Social Media Scraper v2.0
- Runs all three scrapers: Instagram, YouTube, TikTok
- Three modes: custom (default 100 posts), deep (2 years/unlimited), test (15 posts)
- For Instagram deep scrape: defaults to 2 years, with option for "deep deep" (all posts)
- Interrupt handler for graceful shutdown
- Google Drive upload support (when rclone is configured)
"""

import os
import sys
import json
import time
import argparse
import signal
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# Add the scrapers directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the actual scrapers from the same directory
from instagram_scraper import InstagramScraper, ACCOUNTS_TO_TRACK as INSTA_ACCOUNTS
from youtube_scraper import YoutubeScraper, ACCOUNTS_TO_TRACK as YOUTUBE_ACCOUNTS
from tiktok_scraper import TikTokScraper


class MasterScraper:
    """Master scraper that orchestrates Instagram, YouTube, and TikTok scrapers"""
    
    # Default accounts for testing
    DEFAULT_TEST_ACCOUNT = "popdartsgame"
    
    def __init__(self):
        self.interrupted = False
        self.scrapers = {}
        self.results = {}
        
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
    
    def get_scrape_mode(self):
        """Get scraping mode and configuration from user"""
        print("\n" + "="*70)
        print("🎯 MASTER SCRAPER - SELECT MODE")
        print("="*70)
        print("\n1. Default mode (100 Instagram, 100 TikTok, ALL YouTube)")
        print("2. Custom mode (specify posts per platform)")
        print("3. Test mode (30 posts per account, terminal display only)")
        print()
        
        while True:
            choice = input("Enter your choice (1, 2, or 3): ").strip()
            
            if choice == '1' or choice == '':
                return {
                    'mode': 'default',
                    'instagram_posts': 100,
                    'tiktok_posts': 100,
                    'youtube_posts': None,  # None means all videos
                    'test_mode': False,
                    'test_account': None
                }
                    
            elif choice == '2':
                # Ask for posts per platform
                print("\n📊 Custom Mode - Specify posts per platform")
                print("(Press Enter for default values)")
                
                instagram_input = input("\nInstagram posts per account [100]: ").strip()
                instagram_posts = int(instagram_input) if instagram_input else 100
                
                tiktok_input = input("TikTok posts per account [100]: ").strip()
                tiktok_posts = int(tiktok_input) if tiktok_input else 100
                
                youtube_input = input("YouTube videos per channel (Enter 'all' for all videos) [all]: ").strip().lower()
                if youtube_input == '' or youtube_input == 'all':
                    youtube_posts = None  # All videos
                else:
                    try:
                        youtube_posts = int(youtube_input)
                    except ValueError:
                        print("Invalid input, using 'all'")
                        youtube_posts = None
                
                return {
                    'mode': 'custom',
                    'instagram_posts': instagram_posts,
                    'tiktok_posts': tiktok_posts,
                    'youtube_posts': youtube_posts,
                    'test_mode': False,
                    'test_account': None
                }
                        
            elif choice == '3':
                return {
                    'mode': 'test',
                    'instagram_posts': 30,
                    'tiktok_posts': 30,
                    'youtube_posts': 30,
                    'test_mode': True,
                    'test_account': 'popdartsgame'  # Only test this account
                }
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
    
    def select_platforms(self):
        """Let user select which platforms to scrape"""
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
            choice = input("Enter your choice (1-5, default=1): ").strip()
            
            if choice == '' or choice == '1':
                return {'instagram': True, 'youtube': True, 'tiktok': True}
            elif choice == '2':
                return {'instagram': True, 'youtube': False, 'tiktok': False}
            elif choice == '3':
                return {'instagram': False, 'youtube': True, 'tiktok': False}
            elif choice == '4':
                return {'instagram': False, 'youtube': False, 'tiktok': True}
            elif choice == '5':
                platforms = {'instagram': False, 'youtube': False, 'tiktok': False}
                print("\nSelect platforms (y/n for each):")
                platforms['instagram'] = input("  Instagram? (y/n): ").strip().lower() == 'y'
                platforms['youtube'] = input("  YouTube? (y/n): ").strip().lower() == 'y'
                platforms['tiktok'] = input("  TikTok? (y/n): ").strip().lower() == 'y'
                
                if not any(platforms.values()):
                    print("❌ You must select at least one platform!")
                    continue
                return platforms
            else:
                print("Invalid choice. Please enter 1-5.")
    
    def run_instagram_scraper(self, config, auto_mode=False, auto_retry=False):
        """Run the Instagram scraper with the specified configuration"""
        print("\n" + "="*70)
        print("📸 RUNNING INSTAGRAM SCRAPER")
        print("="*70)
        
        try:
            scraper = InstagramScraper()
            
            # For test mode, we'll just use a smaller number and not save
            # The scraper already has auto_mode which skips prompts and saves to files
            # So we'll just run it normally and let it work
            max_posts = config['instagram_posts']
            
            if config['test_mode']:
                print(f"\n🧪 TEST MODE: Scraping {max_posts} posts from @{config['test_account']}")
                # Temporarily replace ACCOUNTS_TO_TRACK with just the test account
                import instagram_scraper
                original_accounts = instagram_scraper.ACCOUNTS_TO_TRACK[:]
                instagram_scraper.ACCOUNTS_TO_TRACK = [config['test_account']]
                try:
                    scraper.run(max_posts=max_posts, auto_mode=True, auto_retry=auto_retry)
                finally:
                    # Restore original accounts
                    instagram_scraper.ACCOUNTS_TO_TRACK = original_accounts
            else:
                if max_posts:
                    print(f"\n📊 Scraping {max_posts} posts per account")
                else:
                    print(f"\n📊 Scraping all available posts per account")
                # Pass parameters to scraper - it will handle everything
                scraper.run(max_posts=max_posts, auto_mode=auto_mode, auto_retry=auto_retry)
            
            return True
            
        except Exception as e:
            print(f"\n❌ Instagram scraper error: {e}")
            traceback.print_exc()
            return False
    
    def run_youtube_scraper(self, config, auto_mode=False, auto_retry=False):
        """Run the YouTube scraper with the specified configuration"""
        print("\n" + "="*70)
        print("🎬 RUNNING YOUTUBE SCRAPER")
        print("="*70)
        
        try:
            scraper = YoutubeScraper()
            
            max_posts = config['youtube_posts']
            
            if config['test_mode']:
                print(f"\n🧪 TEST MODE: Scraping {max_posts} videos from @{config['test_account']}")
                # Temporarily replace ACCOUNTS_TO_TRACK with just the test account
                import youtube_scraper
                original_accounts = youtube_scraper.ACCOUNTS_TO_TRACK[:]
                youtube_scraper.ACCOUNTS_TO_TRACK = [config['test_account']]
                try:
                    scraper.run(max_posts=max_posts, auto_mode=True, auto_retry=auto_retry)
                finally:
                    # Restore original accounts
                    youtube_scraper.ACCOUNTS_TO_TRACK = original_accounts
            else:
                if max_posts is None:
                    print("\n📊 Scraping ALL videos from each channel")
                else:
                    print(f"\n📊 Scraping {max_posts} videos per channel")
                # Pass parameters to scraper - it will handle everything
                scraper.run(max_posts=max_posts, auto_mode=auto_mode, auto_retry=auto_retry)
            
            return True
            
        except Exception as e:
            print(f"\n❌ YouTube scraper error: {e}")
            traceback.print_exc()
            return False
    
    def run_tiktok_scraper(self, config, auto_mode=False, auto_retry=False):
        """Run the TikTok scraper with the specified configuration"""
        print("\n" + "="*70)
        print("🎵 RUNNING TIKTOK SCRAPER")
        print("="*70)
        
        try:
            scraper = TikTokScraper()
            
            max_posts = config['tiktok_posts']
            
            if config['test_mode']:
                print(f"\n🧪 TEST MODE: Scraping {max_posts} posts from @{config['test_account']}")
                # For TikTok, the scraper auto-detects accounts from Excel
                # In test mode, it already has built-in test mode that scrapes popdartsgame
                # We can pass max_posts directly
                scraper.run(max_posts=max_posts, auto_mode=True, auto_retry=auto_retry)
            else:
                print(f"\n📊 Scraping {max_posts} posts per account")
                # Pass parameters to scraper - it will handle everything
                scraper.run(max_posts=max_posts, auto_mode=auto_mode, auto_retry=auto_retry)
            
            return True
            
        except Exception as e:
            print(f"\n❌ TikTok scraper error: {e}")
            traceback.print_exc()
            return False
    
    def display_summary(self, platforms, results):
        """Display final summary of all scraping operations"""
        print("\n" + "="*70)
        print("✅ MASTER SCRAPER COMPLETE!")
        print("="*70)
        
        print("\n📊 Summary:")
        for platform, enabled in platforms.items():
            if enabled:
                status = "✅ Completed" if results.get(platform, False) else "❌ Failed"
                print(f"   {platform.capitalize()}: {status}")
        
        print("\n📁 Output Files:")
        if platforms.get('instagram'):
            print("   • instagram_reels_analytics_tracker.xlsx")
        if platforms.get('youtube'):
            print("   • youtube_analytics_tracker.xlsx")
        if platforms.get('tiktok'):
            print("   • tiktok_analytics_tracker.xlsx")
        
        print("\n🌐 View analytics at: https://crespo.world/crespomize.html")
        print("="*70 + "\n")
    
    def run(self):
        """Main execution function"""
        print("\n" + "="*70)
        print("🚀 MASTER SOCIAL MEDIA SCRAPER v2.0")
        print("="*70)
        print("\nThis tool runs Instagram, YouTube, and TikTok scrapers")
        print("with unified configuration and mode selection.")
        
        # Get configuration
        config = self.get_scrape_mode()
        platforms = self.select_platforms()
        
        # Display configuration
        print("\n" + "="*70)
        print("📋 CONFIGURATION SUMMARY")
        print("="*70)
        mode_desc = {
            'default': f"Default (Instagram: 100, TikTok: 100, YouTube: ALL)",
            'custom': f"Custom (Instagram: {config['instagram_posts']}, TikTok: {config['tiktok_posts']}, YouTube: {config['youtube_posts'] or 'ALL'})",
            'test': f"Test (30 posts per account - for quick verification)"
        }
        print(f"   Mode: {mode_desc[config['mode']]}")
        print(f"   Platforms: {', '.join([p.capitalize() for p, enabled in platforms.items() if enabled])}")
        
        if config['test_mode']:
            print("\n⚠️  TEST MODE: Scraping smaller samples. Files WILL be updated.")
            print("   Tip: You can interrupt (Ctrl+C) after seeing initial results.")
        
        input("\n▶️  Press ENTER to start scraping...")
        
        results = {}
        
        # Run each selected platform's scraper
        if platforms.get('instagram'):
            results['instagram'] = self.run_instagram_scraper(config, auto_mode=False, auto_retry=False)
            if self.interrupted:
                return
        
        if platforms.get('youtube'):
            results['youtube'] = self.run_youtube_scraper(config, auto_mode=False, auto_retry=False)
            if self.interrupted:
                return
        
        if platforms.get('tiktok'):
            results['tiktok'] = self.run_tiktok_scraper(config, auto_mode=False, auto_retry=False)
            if self.interrupted:
                return
        
        # Display final summary
        self.display_summary(platforms, results)
        
        return results


def main():
    """Main entry point with optional command line arguments"""
    parser = argparse.ArgumentParser(
        description='Master Social Media Scraper - runs Instagram, YouTube, and TikTok scrapers'
    )
    parser.add_argument(
        '--mode',
        choices=['default', 'custom', 'test'],
        help='Scraping mode: default (100/100/all), custom (specify per platform), or test (30 posts, terminal only)'
    )
    parser.add_argument(
        '--instagram-posts',
        type=int,
        default=100,
        help='Number of Instagram posts to scrape per account (only for custom mode)'
    )
    parser.add_argument(
        '--tiktok-posts',
        type=int,
        default=100,
        help='Number of TikTok posts to scrape per account (only for custom mode)'
    )
    parser.add_argument(
        '--youtube-posts',
        help='Number of YouTube videos to scrape per channel, or "all" for all videos (only for custom mode)'
    )
    parser.add_argument(
        '--platform',
        choices=['all', 'instagram', 'youtube', 'tiktok'],
        default='all',
        help='Platform to scrape (default: all)'
    )
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Run in non-interactive mode (no prompts, use defaults)'
    )
    parser.add_argument(
        '--auto-retry-once',
        action='store_true',
        help='Automatically retry failed scrapes once'
    )
    
    args = parser.parse_args()
    
    # Create and run master scraper
    scraper = MasterScraper()
    
    try:
        # Use command-line mode if any CLI args provided
        use_cli_mode = (args.mode is not None) or args.non_interactive
        
        if use_cli_mode:
            # Build config from command line args
            if args.mode == 'default':
                config = {
                    'mode': 'default',
                    'instagram_posts': 100,
                    'tiktok_posts': 100,
                    'youtube_posts': None,  # All videos
                    'test_mode': False,
                    'test_account': None
                }
            elif args.mode == 'test':
                config = {
                    'mode': 'test',
                    'instagram_posts': 30,
                    'tiktok_posts': 30,
                    'youtube_posts': 30,
                    'test_mode': True,
                    'test_account': 'popdartsgame'  # Only test this account
                }
            elif args.mode == 'custom' or args.non_interactive:
                # Parse youtube_posts argument
                if args.youtube_posts:
                    if args.youtube_posts.lower() == 'all':
                        youtube_posts = None
                    else:
                        try:
                            youtube_posts = int(args.youtube_posts)
                        except ValueError:
                            print(f"Warning: Invalid youtube-posts value '{args.youtube_posts}', using 'all'")
                            youtube_posts = None
                else:
                    youtube_posts = None  # Default to all for custom mode
                
                config = {
                    'mode': 'custom',
                    'instagram_posts': args.instagram_posts,
                    'tiktok_posts': args.tiktok_posts,
                    'youtube_posts': youtube_posts,
                    'test_mode': False,
                    'test_account': None
                }
            
            # For test mode, always test all platforms
            if config['mode'] == 'test':
                platforms = {
                    'instagram': True,
                    'youtube': True,
                    'tiktok': True
                }
            else:
                platforms = {
                    'instagram': args.platform in ['all', 'instagram'],
                    'youtube': args.platform in ['all', 'youtube'],
                    'tiktok': args.platform in ['all', 'tiktok']
                }
            
            print("\n" + "="*70)
            print("🚀 MASTER SOCIAL MEDIA SCRAPER v2.0")
            print("="*70)
            print(f"\nMode: {config['mode']}")
            if config['mode'] == 'test':
                print(f"Testing account: @{config['test_account']}")
                print(f"Posts per platform: 30")
                print(f"Platforms: All (Instagram, YouTube, TikTok)")
            else:
                print(f"Platform: {args.platform}")
                print(f"Instagram: {config['instagram_posts']} posts")
                print(f"TikTok: {config['tiktok_posts']} posts")
                print(f"YouTube: {config['youtube_posts'] if config['youtube_posts'] else 'ALL'} videos")
            if args.non_interactive:
                print("Non-interactive: Yes")
            if args.auto_retry_once:
                print("Auto-retry: Yes")
            
            results = {}
            
            if platforms.get('instagram'):
                results['instagram'] = scraper.run_instagram_scraper(
                    config, auto_mode=args.non_interactive, auto_retry=args.auto_retry_once
                )
            
            if platforms.get('youtube'):
                results['youtube'] = scraper.run_youtube_scraper(
                    config, auto_mode=args.non_interactive, auto_retry=args.auto_retry_once
                )
            
            if platforms.get('tiktok'):
                results['tiktok'] = scraper.run_tiktok_scraper(
                    config, auto_mode=args.non_interactive, auto_retry=args.auto_retry_once
                )
            
            if not config['test_mode']:
                scraper.display_summary(platforms, results)
        else:
            # Interactive mode
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
