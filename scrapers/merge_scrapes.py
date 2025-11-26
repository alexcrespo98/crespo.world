#!/usr/bin/env python3
"""
Instagram Scrape Merger - Aligns hover and arrow scrape data using sequence alignment algorithms.

Uses like counts as the alignment signal, similar to DNA sequence alignment.
Handles insertions/deletions (extra posts in one scrape but not the other).
"""

import pandas as pd
import os
from datetime import datetime

# Input files
HOVER_FILE = "instagram_hover_scrape.xlsx"
ARROW_FILE = "instagram_arrow_scrape.xlsx"
OUTPUT_FILE = "instagram_merged.xlsx"

def load_scrape_data(hover_file, arrow_file):
    """Load both scrape files and return data per account."""
    hover_xl = pd.ExcelFile(hover_file)
    arrow_xl = pd.ExcelFile(arrow_file)
    
    accounts = {}
    for sheet in hover_xl.sheet_names:
        if sheet in arrow_xl.sheet_names:
            hover_df = pd.read_excel(hover_file, sheet_name=sheet, skiprows=5)
            arrow_df = pd.read_excel(arrow_file, sheet_name=sheet, skiprows=5)
            
            # Get metadata
            meta_df = pd.read_excel(hover_file, sheet_name=sheet, nrows=4)
            followers = meta_df.iloc[1, 1] if len(meta_df) > 1 else None
            
            accounts[sheet] = {
                'hover': hover_df,
                'arrow': arrow_df,
                'followers': followers
            }
    
    return accounts

def normalize_likes(val):
    """Convert likes to integer, handling various formats."""
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).replace(',', '').strip()
    try:
        return int(float(s))
    except:
        return None

def likes_match(a, b, tolerance=0.15):
    """Check if two like counts match within tolerance (default 15%)."""
    if a is None or b is None:
        return False
    if a == 0 and b == 0:
        return True
    max_val = max(a, b)
    if max_val == 0:
        return a == b
    diff_pct = abs(a - b) / max_val
    return diff_pct <= tolerance

def needleman_wunsch_align(hover_likes, arrow_likes, match_score=2, mismatch_penalty=-1, gap_penalty=-1):
    """
    Needleman-Wunsch global sequence alignment algorithm.
    Aligns hover_likes with arrow_likes, allowing for gaps (insertions/deletions).
    
    Returns: List of tuples (hover_idx, arrow_idx) where None means a gap.
    """
    n = len(hover_likes)
    m = len(arrow_likes)
    
    # Initialize scoring matrix
    score = [[0] * (m + 1) for _ in range(n + 1)]
    
    # Initialize gap penalties
    for i in range(n + 1):
        score[i][0] = i * gap_penalty
    for j in range(m + 1):
        score[0][j] = j * gap_penalty
    
    # Fill the matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = score[i-1][j-1] + (match_score if likes_match(hover_likes[i-1], arrow_likes[j-1]) else mismatch_penalty)
            delete = score[i-1][j] + gap_penalty  # Gap in arrow
            insert = score[i][j-1] + gap_penalty  # Gap in hover
            score[i][j] = max(match, delete, insert)
    
    # Traceback
    alignment = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            match = score[i-1][j-1] + (match_score if likes_match(hover_likes[i-1], arrow_likes[j-1]) else mismatch_penalty)
            if score[i][j] == match:
                alignment.append((i-1, j-1))
                i -= 1
                j -= 1
                continue
        
        if i > 0 and score[i][j] == score[i-1][j] + gap_penalty:
            alignment.append((i-1, None))  # Gap in arrow
            i -= 1
        else:
            alignment.append((None, j-1))  # Gap in hover
            j -= 1
    
    alignment.reverse()
    return alignment

def smith_waterman_align(hover_likes, arrow_likes, match_score=2, mismatch_penalty=-1, gap_penalty=-1):
    """
    Smith-Waterman local alignment algorithm.
    Finds the best local alignment between subsequences.
    
    Returns: List of tuples (hover_idx, arrow_idx) for the best local alignment.
    """
    n = len(hover_likes)
    m = len(arrow_likes)
    
    # Initialize scoring matrix
    score = [[0] * (m + 1) for _ in range(n + 1)]
    max_score = 0
    max_pos = (0, 0)
    
    # Fill the matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = score[i-1][j-1] + (match_score if likes_match(hover_likes[i-1], arrow_likes[j-1]) else mismatch_penalty)
            delete = score[i-1][j] + gap_penalty
            insert = score[i][j-1] + gap_penalty
            score[i][j] = max(0, match, delete, insert)  # Local alignment allows 0
            
            if score[i][j] > max_score:
                max_score = score[i][j]
                max_pos = (i, j)
    
    # Traceback from max score position
    alignment = []
    i, j = max_pos
    while i > 0 and j > 0 and score[i][j] > 0:
        match = score[i-1][j-1] + (match_score if likes_match(hover_likes[i-1], arrow_likes[j-1]) else mismatch_penalty)
        if score[i][j] == match:
            alignment.append((i-1, j-1))
            i -= 1
            j -= 1
        elif score[i][j] == score[i-1][j] + gap_penalty:
            alignment.append((i-1, None))
            i -= 1
        else:
            alignment.append((None, j-1))
            j -= 1
    
    alignment.reverse()
    return alignment, max_score

def greedy_chain_align(hover_likes, arrow_likes, tolerance=0.15):
    """
    Greedy chaining approach - find matching pairs and chain them together.
    Good for handling multiple insertions/deletions.
    """
    # Find all matching pairs
    matches = []
    for i, h_like in enumerate(hover_likes):
        for j, a_like in enumerate(arrow_likes):
            if likes_match(h_like, a_like, tolerance):
                matches.append((i, j))
    
    # Sort by hover index, then arrow index
    matches.sort()
    
    # Chain: select matches that form an increasing sequence in both indices
    chain = []
    last_j = -1
    for i, j in matches:
        if j > last_j:
            chain.append((i, j))
            last_j = j
    
    return chain

def sliding_window_align(hover_likes, arrow_likes, window_size=10, tolerance=0.15):
    """
    Sliding window approach - find best offset for chunks of data.
    Handles cases where offset changes partway through.
    """
    alignments = []
    h_idx = 0
    a_idx = 0
    
    while h_idx < len(hover_likes):
        # Find best offset for this window
        best_offset = 0
        best_matches = 0
        
        for offset in range(-5, 20):
            matches = 0
            for w in range(min(window_size, len(hover_likes) - h_idx)):
                a_test = a_idx + w + offset
                if 0 <= a_test < len(arrow_likes):
                    if likes_match(hover_likes[h_idx + w], arrow_likes[a_test], tolerance):
                        matches += 1
            if matches > best_matches:
                best_matches = matches
                best_offset = offset
        
        # Apply this offset for the window
        for w in range(min(window_size, len(hover_likes) - h_idx)):
            a_match = a_idx + w + best_offset
            if 0 <= a_match < len(arrow_likes):
                alignments.append((h_idx + w, a_match))
            else:
                alignments.append((h_idx + w, None))
        
        h_idx += window_size
        a_idx += window_size + best_offset
    
    return alignments

def merge_account(hover_df, arrow_df, method='needleman_wunsch'):
    """
    Merge hover and arrow data for a single account using specified alignment method.
    """
    # Extract likes from both dataframes
    hover_likes = [normalize_likes(x) for x in hover_df['Likes'].tolist()]
    arrow_likes = [normalize_likes(x) for x in arrow_df['Likes'].tolist()]
    
    print(f"    Hover: {len(hover_likes)} posts, Arrow: {len(arrow_likes)} posts")
    print(f"    Hover likes sample: {hover_likes[:5]}")
    print(f"    Arrow likes sample: {arrow_likes[:5]}")
    
    # Run alignment based on method
    if method == 'needleman_wunsch':
        alignment = needleman_wunsch_align(hover_likes, arrow_likes)
        print(f"    Needleman-Wunsch alignment: {len(alignment)} pairs")
    elif method == 'smith_waterman':
        alignment, score = smith_waterman_align(hover_likes, arrow_likes)
        print(f"    Smith-Waterman alignment: {len(alignment)} pairs (score: {score})")
    elif method == 'greedy_chain':
        alignment = greedy_chain_align(hover_likes, arrow_likes)
        print(f"    Greedy chain alignment: {len(alignment)} matched pairs")
    elif method == 'sliding_window':
        alignment = sliding_window_align(hover_likes, arrow_likes)
        print(f"    Sliding window alignment: {len(alignment)} pairs")
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Build merged dataframe
    merged_rows = []
    matches = 0
    gaps_hover = 0
    gaps_arrow = 0
    
    for pair in alignment:
        h_idx, a_idx = pair
        
        row = {}
        
        if h_idx is not None:
            h_row = hover_df.iloc[h_idx]
            row['Position'] = h_idx + 1
            row['Reel ID'] = h_row.get('Reel ID', '')
            row['Views'] = h_row.get('Views', '')
            row['Hover Likes'] = h_row.get('Likes', '')
            row['Comments'] = h_row.get('Comments', '')
            row['URL'] = h_row.get('URL', '')
        else:
            gaps_hover += 1
            row['Position'] = ''
            row['Reel ID'] = '[GAP - not in hover]'
            row['Views'] = ''
            row['Hover Likes'] = ''
            row['Comments'] = ''
            row['URL'] = ''
        
        if a_idx is not None:
            a_row = arrow_df.iloc[a_idx]
            row['Date'] = a_row.get('Date', '')
            row['Date (ISO)'] = a_row.get('Date (ISO)', '')
            row['Arrow Likes'] = a_row.get('Likes', '')
        else:
            gaps_arrow += 1
            row['Date'] = '[GAP - not in arrow]'
            row['Date (ISO)'] = ''
            row['Arrow Likes'] = ''
        
        # Check if likes match
        if h_idx is not None and a_idx is not None:
            h_like = normalize_likes(row['Hover Likes'])
            a_like = normalize_likes(row['Arrow Likes'])
            if likes_match(h_like, a_like):
                row['Match'] = '✓'
                matches += 1
            else:
                row['Match'] = '✗'
        else:
            row['Match'] = '-'
        
        merged_rows.append(row)
    
    print(f"    Matches: {matches}/{len(alignment)} ({100*matches/len(alignment) if alignment else 0:.1f}%)")
    print(f"    Gaps in hover: {gaps_hover}, Gaps in arrow: {gaps_arrow}")
    
    return pd.DataFrame(merged_rows)

def run_all_methods(hover_df, arrow_df):
    """Run all alignment methods and return results for comparison."""
    methods = ['needleman_wunsch', 'greedy_chain', 'sliding_window']
    results = {}
    
    for method in methods:
        print(f"\n  Testing {method}...")
        merged = merge_account(hover_df, arrow_df, method=method)
        matches = len([r for _, r in merged.iterrows() if r.get('Match') == '✓'])
        results[method] = {
            'merged': merged,
            'matches': matches,
            'total': len(merged)
        }
    
    # Find best method
    best = max(results.items(), key=lambda x: x[1]['matches'])
    print(f"\n  🏆 Best method: {best[0]} with {best[1]['matches']}/{best[1]['total']} matches")
    
    return results, best[0]

def main():
    print("="*70)
    print("📊 Instagram Scrape Merger")
    print("="*70)
    
    # Check files exist
    if not os.path.exists(HOVER_FILE):
        print(f"❌ Hover file not found: {HOVER_FILE}")
        return
    if not os.path.exists(ARROW_FILE):
        print(f"❌ Arrow file not found: {ARROW_FILE}")
        return
    
    print(f"📁 Loading {HOVER_FILE} and {ARROW_FILE}...")
    accounts = load_scrape_data(HOVER_FILE, ARROW_FILE)
    print(f"✅ Found {len(accounts)} account(s)")
    
    # Ask for method
    print("\n🔧 Alignment methods available:")
    print("  1. Needleman-Wunsch (global alignment - DNA-style)")
    print("  2. Greedy Chain (find matching pairs, chain together)")
    print("  3. Sliding Window (adaptive offset per chunk)")
    print("  4. Try ALL methods and pick best")
    
    choice = input("\nSelect method (1-4, default=4): ").strip()
    
    methods_map = {
        '1': 'needleman_wunsch',
        '2': 'greedy_chain', 
        '3': 'sliding_window',
        '4': 'all'
    }
    method = methods_map.get(choice, 'all')
    
    # Process each account
    merged_accounts = {}
    
    for account, data in accounts.items():
        print(f"\n{'='*70}")
        print(f"📱 Processing {account}")
        print("="*70)
        
        hover_df = data['hover']
        arrow_df = data['arrow']
        
        if method == 'all':
            results, best_method = run_all_methods(hover_df, arrow_df)
            merged_accounts[account] = results[best_method]['merged']
        else:
            merged = merge_account(hover_df, arrow_df, method=method)
            merged_accounts[account] = merged
    
    # Save results
    print(f"\n💾 Saving to {OUTPUT_FILE}...")
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        for account, df in merged_accounts.items():
            sheet_name = account[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"✅ Merged data saved to {OUTPUT_FILE}")
    print("="*70)

if __name__ == "__main__":
    main()
