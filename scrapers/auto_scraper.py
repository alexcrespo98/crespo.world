#!/usr/bin/env python3
"""
Auto Scraper - Automated Daily Social Media Scraping
Runs master scraper daily at 6:00 AM with predefined configuration
"""

import os
import sys
import logging
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import signal
import atexit

# Setup logging
LOG_FILE = "auto_scraper.log"
PID_FILE = "auto_scraper.pid"

# Configuration
SCRAPE_CONFIG = {
    'schedule_hour': 8,  # 8 AM
    'schedule_minute': 0,
    'auto_retry': True
}

class AutoScraper:
    def __init__(self):
        self.setup_logging()
        self.scheduler = BlockingScheduler()
        self.pid_file = Path(__file__).parent / PID_FILE
        
    def setup_logging(self):
        """Setup rotating log file"""
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        logging.getLogger('').addHandler(console)
    
    def create_pid_file(self):
        """Create PID file to prevent multiple instances"""
        if self.pid_file.exists():
            logging.error(f"PID file exists. Another instance may be running.")
            sys.exit(1)
        self.pid_file.write_text(str(os.getpid()))
        atexit.register(self.remove_pid_file)
    
    def remove_pid_file(self):
        """Remove PID file on exit"""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def run_scrape_job(self):
        """Execute the scraping job"""
        logging.info("="*70)
        logging.info("Starting automated scrape job")
        logging.info("="*70)
        
        try:
            # Build command for master scraper
            script_dir = Path(__file__).parent
            master_script = script_dir / "master_scraper.py"
            
            # Run master scraper with default mode
            cmd = [
                sys.executable,
                str(master_script),
                "--mode", "default",
                "--platform", "all",
                "--non-interactive",
                "--auto-retry-once"
            ]
            
            logging.info(f"Running command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(script_dir)
            )
            
            # Log output
            if result.stdout:
                logging.info(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                logging.warning(f"STDERR:\n{result.stderr}")
            
            if result.returncode == 0:
                logging.info("✅ Scrape job completed successfully")
            else:
                logging.error(f"❌ Scrape job failed with return code {result.returncode}")
        
        except Exception as e:
            logging.error(f"❌ Error running scrape job: {e}")
            logging.error(traceback.format_exc())
    
    def start(self):
        """Start the scheduler"""
        self.create_pid_file()
        
        logging.info("🚀 Auto Scraper starting...")
        logging.info(f"⏰ Scheduled to run daily at {SCRAPE_CONFIG['schedule_hour']:02d}:{SCRAPE_CONFIG['schedule_minute']:02d}")
        
        # Add job
        self.scheduler.add_job(
            self.run_scrape_job,
            CronTrigger(
                hour=SCRAPE_CONFIG['schedule_hour'],
                minute=SCRAPE_CONFIG['schedule_minute']
            ),
            id='daily_scrape',
            name='Daily Social Media Scrape',
            replace_existing=True
        )
        
        # Run immediately on first start (optional - remove if you don't want this)
        logging.info("Running initial scrape job...")
        self.run_scrape_job()
        
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logging.info("⚠️  Scheduler stopped")
            self.remove_pid_file()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Auto Scraper - Daily automated social media scraping')
    parser.add_argument('--start', action='store_true', help='Start the auto scraper')
    parser.add_argument('--stop', action='store_true', help='Stop the auto scraper')
    parser.add_argument('--status', action='store_true', help='Check status')
    parser.add_argument('--run-now', action='store_true', help='Run scrape job immediately')
    
    args = parser.parse_args()
    
    scraper = AutoScraper()
    
    if args.stop:
        pid_file = Path(__file__).parent / PID_FILE
        if pid_file.exists():
            pid = int(pid_file.read_text())
            os.kill(pid, signal.SIGTERM)
            print(f"✅ Stopped auto scraper (PID: {pid})")
        else:
            print("⚠️  No running instance found")
    
    elif args.status:
        pid_file = Path(__file__).parent / PID_FILE
        if pid_file.exists():
            pid = int(pid_file.read_text())
            print(f"✅ Auto scraper is running (PID: {pid})")
        else:
            print("❌ Auto scraper is not running")
    
    elif args.run_now:
        scraper.run_scrape_job()
    
    else:
        # Default: start
        scraper.start()

if __name__ == "__main__":
    main()
