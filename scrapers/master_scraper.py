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
from youtube_scrape import YoutubeScraper, ACCOUNTS_TO_TRACK as YOUTUBE_ACCOUNTS
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
        print("\n1. Custom scrape (default: 100 posts per platform)")
        print("2. Deep scrape (2 years back, with option for 'deep deep')")
        print("3. Test mode (15 posts on @popdartsgame)")
        print()
        
        while True:
            choice = input("Enter your choice (1, 2, or 3): ").strip()
            
            if choice == '1' or choice == '':
                num_input = input("\nHow many posts per account? (default 100): ").strip()
                try:
                    num_posts = int(num_input) if num_input else 100
                    if num_posts > 0:
                        return {
                            'mode': 'custom',
                            'max_posts': num_posts,
                            'deep_scrape': False,
                            'deep_deep': False,
                            'test_mode': False
                        }
                    else:
                        print("Please enter a positive number.")
                except ValueError:
                    print("Invalid input. Using default: 100")
                    return {
                        'mode': 'custom',
                        'max_posts': 100,
                        'deep_scrape': False,
                        'deep_deep': False,
                        'test_mode': False
                    }
                    
            elif choice == '2':
                print("\n⚠️  Deep scrape options:")
                print("   a) 2 years back (default)")
                print("   b) All the way back (DEEP DEEP - takes significantly longer)")
                deep_choice = input("\nEnter 'a' for 2 years or 'b' for all the way back (default=a): ").strip().lower()
                
                if deep_choice == 'b':
                    confirm = input("\n🔥 DEEP DEEP mode will scrape ALL available posts. This takes significantly longer. Continue? (y/n): ").strip().lower()
                    if confirm == 'y':
                        print("  ✅ Deep deep mode selected - will scrape ALL available posts!")
                        return {
                            'mode': 'deep',
                            'max_posts': None,
                            'deep_scrape': True,
                            'deep_deep': True,
                            'test_mode': False
                        }
                    else:
                        continue
                else:
                    confirm = input("\n⚠️  Deep scrape will go back 2 years. Continue? (y/n): ").strip().lower()
                    if confirm == 'y':
                        print("  ✅ Deep mode selected - will scrape back 2 years")
                        return {
                            'mode': 'deep',
                            'max_posts': None,
                            'deep_scrape': True,
                            'deep_deep': False,
                            'test_mode': False
                        }
                    else:
                        continue
                        
            elif choice == '3':
                return {
                    'mode': 'test',
                    'max_posts': 15,
                    'deep_scrape': False,
                    'deep_deep': False,
                    'test_mode': True
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
    
    def run_instagram_scraper(self, config):
        """Run the Instagram scraper with the specified configuration"""
        print("\n" + "="*70)
        print("📸 RUNNING INSTAGRAM SCRAPER")
        print("="*70)
        
        try:
            scraper = InstagramScraper()
            
            if config['test_mode']:
                print(f"\n🧪 TEST MODE: Scraping 15 reels from @{self.DEFAULT_TEST_ACCOUNT}")
            elif config['deep_scrape']:
                if config['deep_deep']:
                    print("\n🔥 DEEP DEEP MODE: Scraping ALL available reels")
                else:
                    print("\n🔍 DEEP MODE: Scraping back 2 years")
            else:
                print(f"\n📊 CUSTOM MODE: Scraping {config['max_posts']} reels per account")
            
            # Note: The Instagram scraper has its own run() method which prompts for mode
            # For master scraper integration, we call run() and let user interact with it
            scraper.run()
            
            return True
            
        except Exception as e:
            print(f"\n❌ Instagram scraper error: {e}")
            traceback.print_exc()
            return False
    
    def run_youtube_scraper(self, config):
        """Run the YouTube scraper with the specified configuration"""
        print("\n" + "="*70)
        print("🎬 RUNNING YOUTUBE SCRAPER")
        print("="*70)
        
        try:
            scraper = YoutubeScraper()
            
            if config['test_mode']:
                print(f"\n🧪 TEST MODE: Scraping 10 videos from @{YOUTUBE_ACCOUNTS[0]}")
            elif config['deep_scrape']:
                print("\n🔥 DEEP MODE: Scraping ALL available videos")
            else:
                print(f"\n📊 CUSTOM MODE: Scraping {config['max_posts']} videos per channel")
            
            # Note: The YouTube scraper has its own run() method which prompts for mode
            # For master scraper integration, we call run() and let user interact
            scraper.run()
            
            return True
            
        except Exception as e:
            print(f"\n❌ YouTube scraper error: {e}")
            traceback.print_exc()
            return False
    
    def run_tiktok_scraper(self, config):
        """Run the TikTok scraper with the specified configuration"""
        print("\n" + "="*70)
        print("🎵 RUNNING TIKTOK SCRAPER")
        print("="*70)
        
        try:
            scraper = TikTokScraper()
            
            if config['test_mode']:
                print(f"\n🧪 TEST MODE: Scraping 15 videos from @{self.DEFAULT_TEST_ACCOUNT}")
            elif config['deep_scrape']:
                print("\n🔥 DEEP MODE: Scraping ALL available videos")
            else:
                print(f"\n📊 CUSTOM MODE: Scraping {config['max_posts']} videos per account")
            
            # The TikTok scraper has its own run() method
            scraper.run()
            
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
        mode_name = {
            'custom': f"Custom ({config['max_posts']} posts)",
            'deep': "Deep (2 years)" if not config['deep_deep'] else "Deep Deep (ALL posts)",
            'test': "Test (15 posts)"
        }
        print(f"   Mode: {mode_name[config['mode']]}")
        print(f"   Platforms: {', '.join([p.capitalize() for p, enabled in platforms.items() if enabled])}")
        
        input("\n▶️  Press ENTER to start scraping...")
        
        results = {}
        
        # Run each selected platform's scraper
        if platforms.get('instagram'):
            results['instagram'] = self.run_instagram_scraper(config)
            if self.interrupted:
                return
        
        if platforms.get('youtube'):
            results['youtube'] = self.run_youtube_scraper(config)
            if self.interrupted:
                return
        
        if platforms.get('tiktok'):
            results['tiktok'] = self.run_tiktok_scraper(config)
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
        choices=['custom', 'deep', 'test'],
        help='Scraping mode: custom (default 100 posts), deep (2 years/all), or test (15 posts)'
    )
    parser.add_argument(
        '--posts',
        type=int,
        default=100,
        help='Number of posts to scrape per account (only for custom mode)'
    )
    parser.add_argument(
        '--deep-deep',
        action='store_true',
        help='For deep mode: scrape ALL posts instead of 2 years'
    )
    parser.add_argument(
        '--platform',
        choices=['all', 'instagram', 'youtube', 'tiktok'],
        default='all',
        help='Platform to scrape (default: all)'
    )
    
    args = parser.parse_args()
    
    # Create and run master scraper
    scraper = MasterScraper()
    
    try:
        # If command line args provided, use them; otherwise use interactive mode
        if args.mode:
            # Build config from command line args
            config = {
                'mode': args.mode,
                'max_posts': args.posts if args.mode == 'custom' else (15 if args.mode == 'test' else None),
                'deep_scrape': args.mode == 'deep',
                'deep_deep': args.deep_deep and args.mode == 'deep',
                'test_mode': args.mode == 'test'
            }
            
            platforms = {
                'instagram': args.platform in ['all', 'instagram'],
                'youtube': args.platform in ['all', 'youtube'],
                'tiktok': args.platform in ['all', 'tiktok']
            }
            
            print("\n" + "="*70)
            print("🚀 MASTER SOCIAL MEDIA SCRAPER v2.0")
            print("="*70)
            print(f"\nMode: {args.mode}")
            print(f"Platform: {args.platform}")
            print(f"Posts: {args.posts}")
            
            results = {}
            
            if platforms.get('instagram'):
                results['instagram'] = scraper.run_instagram_scraper(config)
            
            if platforms.get('youtube'):
                results['youtube'] = scraper.run_youtube_scraper(config)
            
            if platforms.get('tiktok'):
                results['tiktok'] = scraper.run_tiktok_scraper(config)
            
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
