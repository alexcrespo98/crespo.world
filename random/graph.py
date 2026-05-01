#!/usr/bin/env python3
"""
TikTok Analytics Dashboard - Analyze data from tiktok_analytics_tracker.xlsx
Reads multi-account Excel file and creates visualizations
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
from datetime import datetime

class TikTokAnalytics:
    def __init__(self):
        self.excel_file = 'tiktok_analytics_tracker.xlsx'
        self.df = None
        self.account = None
        self.all_sheets = None
    
    def check_excel_file(self):
        """Check if Excel file exists"""
        if not os.path.exists(self.excel_file):
            print(f"❌ File not found: {self.excel_file}")
            print("📝 Make sure you ran the multi-account scraper first!")
            return False
        return True
    
    def load_all_sheets(self):
        """Load all sheet names from Excel file"""
        try:
            self.all_sheets = pd.read_excel(self.excel_file, sheet_name=None)
            return list(self.all_sheets.keys())
        except Exception as e:
            print(f"❌ Error reading Excel file: {e}")
            return None
    
    def choose_account(self):
        """Let user choose which account to analyze"""
        sheets = self.load_all_sheets()
        
        if not sheets:
            print("❌ Could not read Excel sheets!")
            return None
        
        print("\n🎯 Which account would you like to analyze?")
        print("=" * 50)
        
        for i, sheet in enumerate(sheets, 1):
            print(f"{i}. @{sheet}")
        
        print()
        
        while True:
            try:
                choice = int(input("Enter your choice (number): ").strip())
                if 1 <= choice <= len(sheets):
                    self.account = sheets[choice - 1]
                    print(f"✅ Selected: @{self.account}")
                    return self.account
                else:
                    print("❌ Invalid choice. Please try again.")
            except ValueError:
                print("❌ Please enter a number.")
    
    def load_account_data(self):
        """Load data for selected account from Excel"""
        if not self.account:
            return False
        
        try:
            print(f"\n📁 Loading data for @{self.account}...")
            
            # Read the sheet
            raw_df = pd.read_excel(self.excel_file, sheet_name=self.account, index_col=0)
            
            print(f"✅ Loaded {len(raw_df)} rows")
            print(f"✅ Data columns: {list(raw_df.columns)}")
            
            # Extract account-level metrics (followers, total_likes) across all scrapes
            self.account_metrics = {}
            for index, row in raw_df.iterrows():
                if index == 'followers':
                    self.account_metrics['followers'] = row.to_dict()
                elif index == 'total_likes':
                    self.account_metrics['total_likes'] = row.to_dict()
            
            # Parse the data structure
            # Rows are structured as: followers, total_likes, posts_scraped, post_XXX_Date, post_XXX_Views, etc.
            videos_data = []
            
            for index, row in raw_df.iterrows():
                # Extract post data from row names like "post_VIDEO_ID_Metric"
                if index.startswith('post_'):
                    parts = index.split('_')
                    if len(parts) >= 3:
                        metric = parts[-1]  # Last part is the metric (Date, Views, Likes, etc.)
                        
                        # Get the latest column (most recent scrape)
                        latest_value = row.iloc[-1] if len(row) > 0 else None
                        
                        if pd.notna(latest_value):
                            videos_data.append({
                                'index': index,
                                'metric': metric,
                                'value': latest_value
                            })
            
            # Reorganize data by video
            videos_by_id = {}
            for item in videos_data:
                vid_id = '_'.join(item['index'].split('_')[1:-1])
                if vid_id not in videos_by_id:
                    videos_by_id[vid_id] = {}
                videos_by_id[vid_id][item['metric']] = item['value']
            
            # Create clean dataframe
            clean_data = []
            for vid_id, metrics in videos_by_id.items():
                if 'Date' in metrics:
                    clean_data.append({
                        'date': metrics.get('Date'),
                        'views': pd.to_numeric(metrics.get('Views', 0), errors='coerce'),
                        'likes': pd.to_numeric(metrics.get('Likes', 0), errors='coerce'),
                        'comments': pd.to_numeric(metrics.get('Comments', 0), errors='coerce'),
                        'shares': pd.to_numeric(metrics.get('Shares', 0), errors='coerce'),
                        'engagement_rate': pd.to_numeric(metrics.get('EngagementRate', 0), errors='coerce'),
                    })
            
            if not clean_data:
                print("⚠️  No video data found in sheet")
                return False
            
            self.df = pd.DataFrame(clean_data)
            
            # Convert date column
            self.df['date'] = pd.to_datetime(self.df['date'], errors='coerce')
            self.df = self.df.sort_values('date')
            
            print(f"📊 Found {len(self.df)} videos with data")
            print(f"📅 Date range: {self.df['date'].min()} to {self.df['date'].max()}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading account data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def fill_gaps_in_data(self):
        """Fill unrealistic data gaps (like 0s) with interpolated values"""
        if self.df is None:
            return
        
        numeric_cols = ['likes', 'views', 'comments', 'shares']
        
        for col in numeric_cols:
            if col in self.df.columns:
                # Replace 0s with NaN
                self.df.loc[self.df[col] == 0, col] = np.nan
                
                # Interpolate missing values
                self.df[col] = self.df[col].interpolate(method='linear', limit_direction='both')
                
                # Fill any remaining NaNs
                self.df[col] = self.df[col].fillna(method='ffill').fillna(method='bfill')
        
        print("✅ Data gaps filled")
    
    def calculate_daily_stats(self):
        """Calculate stats aggregated by day"""
        if self.df is None or 'date' not in self.df.columns:
            return None
        
        daily = self.df.groupby(self.df['date'].dt.date).agg({
            'likes': 'sum',
            'views': 'sum',
            'comments': 'sum',
            'date': 'count'
        }).rename(columns={'date': 'posts_per_day'})
        
        daily.index = pd.to_datetime(daily.index)
        
        return daily
    
    def calculate_followers_over_time(self):
        """Calculate followers over time from account metrics"""
        if not hasattr(self, 'account_metrics') or 'followers' not in self.account_metrics:
            return None
        
        followers_data = self.account_metrics['followers']
        
        # Convert to list of tuples (date, followers)
        data_points = []
        for col_name, followers_count in followers_data.items():
            if pd.notna(followers_count):
                data_points.append({
                    'timestamp': col_name,  # This is the scrape timestamp
                    'followers': pd.to_numeric(followers_count, errors='coerce')
                })
        
        if data_points:
            followers_df = pd.DataFrame(data_points)
            return followers_df
        
        return None
    
    def demo_dashboard(self):
        """Create demo analytics visualizations"""
        if self.df is None:
            print("❌ No data loaded!")
            return
        
        print("\n🎨 Creating demo dashboard...")
        
        # Fill data gaps first
        self.fill_gaps_in_data()
        
        # Create figure with scrollable subplots
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(16, 20))  # Tall figure for scrolling
        fig.patch.set_facecolor('#0a0a0a')
        
        # Calculate daily stats
        daily = self.calculate_daily_stats()
        followers_over_time = self.calculate_followers_over_time()
        
        # 1. Likes per post over time
        ax1 = plt.subplot(6, 2, 1)
        ax1.set_facecolor('#1a1a1a')
        if 'date' in self.df.columns and 'likes' in self.df.columns:
            valid_data = self.df.dropna(subset=['date', 'likes'])
            ax1.scatter(valid_data['date'], valid_data['likes'], 
                       c='#ff6b6b', s=50, alpha=0.7, edgecolors='#ff4757')
            ax1.plot(valid_data['date'], valid_data['likes'], 
                    color='#ff6b6b', alpha=0.3, linewidth=1)
            ax1.set_title('Likes per Post Over Time', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Likes')
            ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax1.tick_params(axis='x', rotation=45)
            ax1.grid(True, alpha=0.2)
        
        # 2. Views per post over time
        ax2 = plt.subplot(6, 2, 2)
        ax2.set_facecolor('#1a1a1a')
        if 'date' in self.df.columns and 'views' in self.df.columns:
            valid_data = self.df.dropna(subset=['date', 'views'])
            ax2.scatter(valid_data['date'], valid_data['views'], 
                       c='#00d2d3', s=50, alpha=0.7, edgecolors='#00a8a9')
            ax2.plot(valid_data['date'], valid_data['views'], 
                    color='#00d2d3', alpha=0.3, linewidth=1)
            ax2.set_title('Views per Post Over Time', fontsize=12, fontweight='bold')
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Views')
            ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax2.tick_params(axis='x', rotation=45)
            ax2.grid(True, alpha=0.2)
        
        # 3. Followers over time
        ax3 = plt.subplot(6, 2, 3)
        ax3.set_facecolor('#1a1a1a')
        if followers_over_time is not None and not followers_over_time.empty:
            ax3.plot(range(len(followers_over_time)), followers_over_time['followers'], 
                    color='#ffa502', linewidth=3, marker='o', markersize=8, markeredgecolor='#ff8c00')
            ax3.set_title('Followers Growth Over Scrapes', fontsize=12, fontweight='bold')
            ax3.set_xlabel('Scrape #')
            ax3.set_ylabel('Followers')
            ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax3.grid(True, alpha=0.2)
        
        # 4. Comments per post
        ax4 = plt.subplot(6, 2, 4)
        ax4.set_facecolor('#1a1a1a')
        if 'date' in self.df.columns and 'comments' in self.df.columns:
            valid_data = self.df.dropna(subset=['date', 'comments'])
            if not valid_data.empty:
                ax4.scatter(valid_data['date'], valid_data['comments'], 
                           c='#1abc9c', s=50, alpha=0.7, edgecolors='#16a085')
                ax4.plot(valid_data['date'], valid_data['comments'], 
                        color='#1abc9c', alpha=0.3, linewidth=1)
                ax4.set_title('Comments per Post Over Time', fontsize=12, fontweight='bold')
                ax4.set_xlabel('Date')
                ax4.set_ylabel('Comments')
                ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
                ax4.tick_params(axis='x', rotation=45)
                ax4.grid(True, alpha=0.2)
        
        # 5. Likes per day
        ax5 = plt.subplot(6, 2, 5)
        ax5.set_facecolor('#1a1a1a')
        if daily is not None and not daily.empty:
            ax5.bar(daily.index, daily['likes'], color='#ff6b6b', alpha=0.7, edgecolor='#ff4757')
            ax5.set_title('Total Likes per Day', fontsize=12, fontweight='bold')
            ax5.set_xlabel('Date')
            ax5.set_ylabel('Likes')
            ax5.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax5.tick_params(axis='x', rotation=45)
            ax5.grid(True, alpha=0.2, axis='y')
        
        # 6. Shares per post
        ax6 = plt.subplot(6, 2, 6)
        ax6.set_facecolor('#1a1a1a')
        if 'date' in self.df.columns and 'shares' in self.df.columns:
            valid_data = self.df.dropna(subset=['date', 'shares'])
            if not valid_data.empty:
                ax6.scatter(valid_data['date'], valid_data['shares'], 
                           c='#e74c3c', s=50, alpha=0.7, edgecolors='#c0392b')
                ax6.plot(valid_data['date'], valid_data['shares'], 
                        color='#e74c3c', alpha=0.3, linewidth=1)
                ax6.set_title('Shares per Post Over Time', fontsize=12, fontweight='bold')
                ax6.set_xlabel('Date')
                ax6.set_ylabel('Shares')
                ax6.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
                ax6.tick_params(axis='x', rotation=45)
                ax6.grid(True, alpha=0.2)
        
        # 7. Views per day
        ax7 = plt.subplot(6, 2, 7)
        ax7.set_facecolor('#1a1a1a')
        if daily is not None and not daily.empty:
            ax7.bar(daily.index, daily['views'], color='#00d2d3', alpha=0.7, edgecolor='#00a8a9')
            ax7.set_title('Total Views per Day', fontsize=12, fontweight='bold')
            ax7.set_xlabel('Date')
            ax7.set_ylabel('Views')
            ax7.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax7.tick_params(axis='x', rotation=45)
            ax7.grid(True, alpha=0.2, axis='y')
        
        # 8. Posts per day
        ax8 = plt.subplot(6, 2, 8)
        ax8.set_facecolor('#1a1a1a')
        if daily is not None and not daily.empty:
            ax8.bar(daily.index, daily['posts_per_day'], color='#9b59b6', alpha=0.7, edgecolor='#8e44ad')
            ax8.set_title('Posts per Day', fontsize=12, fontweight='bold')
            ax8.set_xlabel('Date')
            ax8.set_ylabel('# Posts')
            ax8.tick_params(axis='x', rotation=45)
            ax8.grid(True, alpha=0.2, axis='y')
        
        # 9. Engagement rate over time
        ax9 = plt.subplot(6, 2, 9)
        ax9.set_facecolor('#1a1a1a')
        if 'date' in self.df.columns and 'likes' in self.df.columns and 'views' in self.df.columns:
            valid_data = self.df.dropna(subset=['date', 'likes', 'views'])
            if not valid_data.empty:
                engagement = (valid_data['likes'] / valid_data['views'] * 100)
                ax9.plot(valid_data['date'], engagement, 
                        color='#2ecc71', linewidth=2, marker='o', markersize=5, alpha=0.7)
                ax9.set_title('Engagement Rate Over Time', fontsize=12, fontweight='bold')
                ax9.set_xlabel('Date')
                ax9.set_ylabel('Engagement %')
                ax9.tick_params(axis='x', rotation=45)
                ax9.grid(True, alpha=0.2)
        
        # 10. Likes vs Views scatter
        ax10 = plt.subplot(6, 2, 10)
        ax10.set_facecolor('#1a1a1a')
        if 'likes' in self.df.columns and 'views' in self.df.columns:
            valid_data = self.df.dropna(subset=['likes', 'views'])
            ax10.scatter(valid_data['views'], valid_data['likes'], 
                        c='#e91e63', s=60, alpha=0.6, edgecolors='#c2185b')
            ax10.set_title('Likes vs Views Correlation', fontsize=12, fontweight='bold')
            ax10.set_xlabel('Views')
            ax10.set_ylabel('Likes')
            ax10.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax10.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: self.format_number(x)))
            ax10.grid(True, alpha=0.2)
        
        # 11. Summary stats (top)
        ax11 = plt.subplot(6, 2, 11)
        ax11.axis('off')
        
        total_likes = self.df['likes'].sum() if 'likes' in self.df.columns else 0
        total_views = self.df['views'].sum() if 'views' in self.df.columns else 0
        avg_likes = self.df['likes'].mean() if 'likes' in self.df.columns else 0
        avg_views = self.df['views'].mean() if 'views' in self.df.columns else 0
        total_posts = len(self.df)
        
        engagement_rate = (total_likes/total_views*100) if total_views > 0 else 0
        
        current_followers = None
        if followers_over_time is not None and not followers_over_time.empty:
            current_followers = followers_over_time['followers'].iloc[-1]
        
        stats_text = f"""📊 SUMMARY STATISTICS

Total Posts: {total_posts}
Total Likes: {self.format_number(total_likes)}
Total Views: {self.format_number(total_views)}
Avg Likes/Post: {self.format_number(avg_likes)}
Avg Views/Post: {self.format_number(avg_views)}

👥 Current Followers:
{self.format_number(current_followers) if current_followers else 'N/A'}

📈 Overall Engagement:
{engagement_rate:.2f}%"""
        
        ax11.text(0.05, 0.95, stats_text, transform=ax11.transAxes,
                fontsize=11, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.8', facecolor='#2a2a2a', alpha=0.9, edgecolor='#444'))
        
        # 12. Comments and Shares summary
        ax12 = plt.subplot(6, 2, 12)
        ax12.axis('off')
        
        total_comments = self.df['comments'].sum() if 'comments' in self.df.columns else 0
        total_shares = self.df['shares'].sum() if 'shares' in self.df.columns else 0
        avg_comments = self.df['comments'].mean() if 'comments' in self.df.columns else 0
        avg_shares = self.df['shares'].mean() if 'shares' in self.df.columns else 0
        
        extra_stats_text = f"""📣 ENGAGEMENT DETAILS

Total Comments: {self.format_number(total_comments)}
Avg Comments/Post: {self.format_number(avg_comments)}

🔄 Total Shares: {self.format_number(total_shares)}
Avg Shares/Post: {self.format_number(avg_shares)}

📅 Date Range:
{self.df['date'].min().strftime('%Y-%m-%d') if 'date' in self.df.columns else 'N/A'}
to
{self.df['date'].max().strftime('%Y-%m-%d') if 'date' in self.df.columns else 'N/A'}"""
        
        ax12.text(0.05, 0.95, extra_stats_text, transform=ax12.transAxes,
                fontsize=11, verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.8', facecolor='#2a2a2a', alpha=0.9, edgecolor='#444'))
        
        plt.suptitle(f'📊 @{self.account} TikTok Analytics Dashboard - SCROLL DOWN TO SEE ALL CHARTS', 
                    fontsize=16, fontweight='bold', color='white', y=0.995)
        
        plt.tight_layout(rect=[0, 0, 1, 0.99])
        
        # Try to maximize the window (works with some backends)
        try:
            mng = plt.get_current_fig_manager()
            if hasattr(mng.window, 'showMaximized'):
                mng.window.showMaximized()
            elif hasattr(mng.window, 'state'):
                mng.window.state('zoomed')  # For Tkinter on Windows
        except:
            pass
        
        plt.show()
        
        print("✅ Dashboard displayed! (Scroll through the window to see all charts)")
    
    def format_number(self, num):
        """Format numbers for display"""
        if np.isnan(num) or num == 0:
            return "0"
        elif num >= 1000000:
            return f'{num/1000000:.1f}M'
        elif num >= 1000:
            return f'{num/1000:.1f}K'
        else:
            return f'{int(num)}'

def main():
    print("🎵 TikTok Analytics Dashboard")
    print("=" * 50)
    
    # Initialize analytics
    analytics = TikTokAnalytics()
    
    # Check if Excel file exists
    if not analytics.check_excel_file():
        return
    
    print(f"✅ Found: {analytics.excel_file}")
    
    # Choose account
    if not analytics.choose_account():
        print("❌ No account selected!")
        return
    
    # Load data
    if not analytics.load_account_data():
        print("❌ Could not load data!")
        return
    
    # Ask what user wants
    print("\n🎯 What would you like to do?")
    print("=" * 50)
    print("1. View demo dashboard")
    print("2. Custom analysis (coming soon)")
    
    while True:
        choice = input("\nEnter your choice (1-2): ").strip()
        
        if choice == '1':
            analytics.demo_dashboard()
            break
        elif choice == '2':
            print("⚠️  Custom analysis coming soon!")
            break
        else:
            print("❌ Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    print("📦 Required: pip install pandas matplotlib numpy openpyxl")
    print()
    main()
