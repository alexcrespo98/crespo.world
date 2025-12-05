#!/usr/bin/env python3
"""
Anomaly Fixer - Standalone script to find and fix anomalies in Instagram scraper data

This script:
1. Reads the instagram_reels_analytics_tracker.xlsx file
2. Finds anomalies (likes < 10, likes > views, likes = views, implausibly low ratios)
3. Attempts to rescrape anomalous posts
4. Asks for user input when auto-fix fails
5. Saves the fixed file and uploads to Google Drive

Usage:
    python anomaly_fixer.py
    python anomaly_fixer.py --depth 200  # Scan 200 posts deep per account
    python anomaly_fixer.py --auto       # Auto-fix mode (no prompts)
"""

import os
import sys
import re
import time
import random
import argparse
import subprocess
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
except ImportError:
    print("❌ pandas not installed. Run: pip install pandas openpyxl")
    sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium not installed. Auto-fix will not work. Run: pip install selenium webdriver-manager")

# Configuration
OUTPUT_EXCEL = "instagram_reels_analytics_tracker.xlsx"

# Anomaly detection thresholds
THRESHOLDS = {
    'min_likes': 10,                    # Flag if likes < 10
    'min_views_for_ratio_check': 1000,  # Only check ratio if views > 1000
    'min_likes_ratio': 0.001,           # Flag if likes < 0.1% of views
    'likes_views_same_threshold': 0.05, # Flag if |likes - views| / views < 5%
}


class AnomalyFixer:
    """Standalone anomaly detection and fixing tool for Instagram scraper data."""
    
    def __init__(self, excel_path=OUTPUT_EXCEL, depth=100, auto_mode=False):
        self.excel_path = excel_path
        self.depth = depth
        self.auto_mode = auto_mode
        self.driver = None
        self.data = {}
        self.anomalies = []
        self.fixes_made = 0
        self.manual_entries = 0
        
    def load_excel(self):
        """Load the Excel file with all account sheets."""
        if not os.path.exists(self.excel_path):
            print(f"❌ File not found: {self.excel_path}")
            print(f"   Make sure you're running from the scrapers directory")
            return False
        
        try:
            self.data = pd.read_excel(self.excel_path, sheet_name=None, index_col=0)
            print(f"✅ Loaded {len(self.data)} accounts from {self.excel_path}")
            for account in self.data.keys():
                print(f"   • @{account}: {len(self.data[account].columns)} scrapes")
            return True
        except Exception as e:
            print(f"❌ Error loading Excel: {e}")
            return False
    
    def find_anomalies(self):
        """Scan all accounts for anomalous data points."""
        print("\n" + "="*70)
        print("🔍 SCANNING FOR ANOMALIES")
        print("="*70)
        
        self.anomalies = []
        
        for account, df in self.data.items():
            print(f"\n📊 Scanning @{account}...")
            account_anomalies = []
            
            # Get list of reel IDs from row names
            reel_ids = set()
            for row_name in df.index:
                if row_name.startswith('reel_') and '_' in row_name:
                    parts = row_name.split('_')
                    if len(parts) >= 2:
                        reel_id = parts[1]
                        reel_ids.add(reel_id)
            
            # Sort and limit to most recent N posts based on depth
            reel_ids = sorted(list(reel_ids))[:self.depth]
            
            for reel_id in reel_ids:
                # Get latest values for this reel
                views_row = f"reel_{reel_id}_views"
                likes_row = f"reel_{reel_id}_likes"
                
                if views_row not in df.index or likes_row not in df.index:
                    continue
                
                # Get the most recent non-null values
                views_series = df.loc[views_row].dropna()
                likes_series = df.loc[likes_row].dropna()
                
                if len(views_series) == 0 or len(likes_series) == 0:
                    continue
                
                # Get latest values (last column with data)
                views = None
                likes = None
                
                for col in reversed(df.columns):
                    if views is None and col in views_series.index:
                        try:
                            views = int(float(views_series[col]))
                        except:
                            pass
                    if likes is None and col in likes_series.index:
                        try:
                            likes = int(float(likes_series[col]))
                        except:
                            pass
                    if views is not None and likes is not None:
                        break
                
                if views is None or likes is None:
                    continue
                
                # Check for anomalies
                anomaly_reasons = []
                
                # Check 1: Likes greater than views (impossible)
                if likes > views:
                    anomaly_reasons.append(f"likes ({likes:,}) > views ({views:,})")
                
                # Check 2: Likes approximately equal to views (extraction error)
                if views > 0 and abs(likes - views) / views < THRESHOLDS['likes_views_same_threshold']:
                    anomaly_reasons.append(f"likes ({likes:,}) ≈ views ({views:,})")
                
                # Check 3: Likes under minimum threshold
                if likes < THRESHOLDS['min_likes'] and views >= THRESHOLDS['min_views_for_ratio_check']:
                    anomaly_reasons.append(f"likes ({likes}) < {THRESHOLDS['min_likes']} for {views:,} views")
                
                # Check 4: Implausibly low likes ratio
                if views >= THRESHOLDS['min_views_for_ratio_check']:
                    if likes / views < THRESHOLDS['min_likes_ratio']:
                        ratio = likes / views * 100
                        anomaly_reasons.append(f"likes ratio too low ({ratio:.3f}%)")
                
                if anomaly_reasons:
                    account_anomalies.append({
                        'account': account,
                        'reel_id': reel_id,
                        'views': views,
                        'likes': likes,
                        'reasons': anomaly_reasons,
                        'url': f"https://www.instagram.com/reel/{reel_id}/"
                    })
            
            if account_anomalies:
                print(f"   ⚠️ Found {len(account_anomalies)} anomalies")
                self.anomalies.extend(account_anomalies)
            else:
                print(f"   ✅ No anomalies found")
        
        print(f"\n📊 Total anomalies found: {len(self.anomalies)}")
        return self.anomalies
    
    def setup_driver(self):
        """Set up Selenium WebDriver for rescraping."""
        if not SELENIUM_AVAILABLE:
            print("❌ Selenium not available. Cannot auto-fix.")
            return None
        
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            
            print("\n🌐 Setting up browser...")
            
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
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            print("✅ Browser ready")
            return self.driver
            
        except Exception as e:
            print(f"❌ Failed to set up browser: {e}")
            return None
    
    def extract_likes_from_page(self, driver):
        """Extract likes count from the current Instagram page."""
        try:
            time.sleep(2)
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            
            # Look for likes patterns
            patterns = [
                r'([\d,]+)\s*likes?',
                r'liked by ([\d,]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, body_text)
                if match:
                    likes_str = match.group(1).replace(',', '')
                    return int(likes_str)
            
            return None
        except Exception as e:
            return None
    
    def fix_anomaly(self, anomaly):
        """Attempt to fix a single anomaly by rescraping or manual entry."""
        reel_id = anomaly['reel_id']
        account = anomaly['account']
        url = anomaly['url']
        
        print(f"\n   🔧 Fixing {reel_id}...")
        print(f"      Current: views={anomaly['views']:,}, likes={anomaly['likes']:,}")
        print(f"      Reasons: {', '.join(anomaly['reasons'])}")
        print(f"      URL: {url}")
        
        new_likes = None
        
        # Try to rescrape
        if self.driver:
            try:
                # Add jitter delay
                delay = random.uniform(2.0, 5.0)
                print(f"      ⏱️ Waiting {delay:.1f}s...")
                time.sleep(delay)
                
                self.driver.get(url)
                time.sleep(3)
                
                new_likes = self.extract_likes_from_page(self.driver)
                
                if new_likes:
                    # Validate the new value
                    is_valid = True
                    if new_likes > anomaly['views']:
                        is_valid = False
                        print(f"      ⚠️ Scraped likes ({new_likes:,}) > views ({anomaly['views']:,}), rejecting")
                    elif anomaly['views'] > 0 and abs(new_likes - anomaly['views']) / anomaly['views'] < THRESHOLDS['likes_views_same_threshold']:
                        is_valid = False
                        print(f"      ⚠️ Scraped likes ({new_likes:,}) ≈ views ({anomaly['views']:,}), rejecting")
                    
                    if is_valid:
                        print(f"      ✅ Scraped new likes: {new_likes:,}")
                    else:
                        new_likes = None
                else:
                    print(f"      ⚠️ Could not extract likes from page")
                    
            except Exception as e:
                print(f"      ❌ Scrape error: {str(e)[:50]}")
        
        # If auto-fix failed and not in auto mode, ask user
        if new_likes is None and not self.auto_mode:
            print(f"      🔗 Please check: {url}")
            user_input = input(f"      Enter correct likes (or Enter to skip): ").strip()
            
            if user_input:
                try:
                    new_likes = int(user_input.replace(',', ''))
                    # Validate the manual entry
                    if new_likes < 0:
                        print(f"      ⚠️ Invalid: likes cannot be negative")
                    elif new_likes > 100000000:  # 100M sanity check
                        print(f"      ⚠️ Invalid: value seems too large")
                    else:
                        print(f"      ✅ User entered: {new_likes:,}")
                        self.manual_entries += 1
                except ValueError:
                    print(f"      ⚠️ Invalid input, skipping")
                    return False
        
        # Apply the fix if we have a new value
        if new_likes is not None:
            # Update the DataFrame
            df = self.data[account]
            likes_row = f"reel_{reel_id}_likes"
            
            if likes_row in df.index:
                # Update the latest column
                latest_col = df.columns[-1]
                df.loc[likes_row, latest_col] = new_likes
                self.data[account] = df
                self.fixes_made += 1
                print(f"      ✅ Fixed: {anomaly['likes']:,} → {new_likes:,}")
                return True
        
        return False
    
    def fix_all_anomalies(self):
        """Fix all detected anomalies."""
        if not self.anomalies:
            print("\n✅ No anomalies to fix!")
            return
        
        print("\n" + "="*70)
        print(f"🔧 FIXING {len(self.anomalies)} ANOMALIES")
        print("="*70)
        
        # Show summary first
        for i, anomaly in enumerate(self.anomalies[:20]):  # Show first 20
            print(f"   {i+1}. @{anomaly['account']}/{anomaly['reel_id']}: {', '.join(anomaly['reasons'])}")
        if len(self.anomalies) > 20:
            print(f"   ... and {len(self.anomalies) - 20} more")
        
        # Confirm
        if not self.auto_mode:
            choice = input(f"\n   Fix all {len(self.anomalies)} anomalies? (y/n/number to limit, default=y): ").strip().lower()
            if choice == 'n':
                print("   ⏭️ Skipping fixes")
                return
            elif choice != 'y' and choice != '':
                try:
                    limit = int(choice)
                    self.anomalies = self.anomalies[:limit]
                    print(f"   📊 Limiting to {limit} anomalies")
                except ValueError:
                    pass
        
        # Set up browser if we have anomalies to fix
        if SELENIUM_AVAILABLE and len(self.anomalies) > 0:
            self.setup_driver()
        
        # Fix each anomaly
        for i, anomaly in enumerate(self.anomalies):
            print(f"\n[{i+1}/{len(self.anomalies)}] @{anomaly['account']}/{anomaly['reel_id']}")
            self.fix_anomaly(anomaly)
        
        # Cleanup
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def save_excel(self):
        """Save the fixed data back to Excel."""
        if self.fixes_made == 0:
            print("\n📊 No fixes to save")
            return
        
        print(f"\n💾 Saving {self.fixes_made} fixes to {self.excel_path}...")
        
        try:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                for account, df in self.data.items():
                    sheet_name = account[:31]  # Excel sheet name limit
                    df.to_excel(writer, sheet_name=sheet_name)
            
            print(f"✅ Saved successfully!")
            return True
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def upload_to_google_drive(self):
        """Upload the fixed file to Google Drive using rclone."""
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
            
            excel_path = os.path.abspath(self.excel_path)
            print(f"\n📤 Uploading {self.excel_path}...")
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
            return False
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return False
    
    def run(self):
        """Main entry point - run the full anomaly detection and fixing workflow."""
        print("\n" + "="*70)
        print("🔧 INSTAGRAM ANOMALY FIXER")
        print("="*70)
        print(f"   Excel file: {self.excel_path}")
        print(f"   Scan depth: {self.depth} posts per account")
        print(f"   Mode: {'Auto' if self.auto_mode else 'Interactive'}")
        print("="*70)
        
        # Load Excel
        if not self.load_excel():
            return
        
        # Find anomalies
        self.find_anomalies()
        
        if not self.anomalies:
            print("\n✅ No anomalies found! Data looks good.")
            return
        
        # Fix anomalies
        self.fix_all_anomalies()
        
        # Save and upload
        if self.fixes_made > 0:
            if self.save_excel():
                # Ask about upload
                if not self.auto_mode:
                    choice = input("\n   Upload to Google Drive? (y/n, default=y): ").strip().lower()
                    if choice != 'n':
                        self.upload_to_google_drive()
                else:
                    self.upload_to_google_drive()
        
        # Summary
        print("\n" + "="*70)
        print("📊 ANOMALY FIXER SUMMARY")
        print("="*70)
        print(f"   Anomalies found: {len(self.anomalies)}")
        print(f"   Fixes applied: {self.fixes_made}")
        print(f"   Manual entries: {self.manual_entries}")
        print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Find and fix anomalies in Instagram scraper data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python anomaly_fixer.py                    # Interactive mode, 100 posts deep
    python anomaly_fixer.py --depth 200        # Scan 200 posts deep per account
    python anomaly_fixer.py --auto             # Auto-fix mode (no prompts)
    python anomaly_fixer.py --file custom.xlsx # Use custom Excel file
        """
    )
    
    parser.add_argument('--depth', type=int, default=100,
                        help='Number of posts to scan per account (default: 100)')
    parser.add_argument('--auto', action='store_true',
                        help='Auto-fix mode (no prompts, skip manual entry)')
    parser.add_argument('--file', type=str, default=OUTPUT_EXCEL,
                        help=f'Excel file to process (default: {OUTPUT_EXCEL})')
    
    args = parser.parse_args()
    
    fixer = AnomalyFixer(
        excel_path=args.file,
        depth=args.depth,
        auto_mode=args.auto
    )
    
    fixer.run()


if __name__ == "__main__":
    main()
