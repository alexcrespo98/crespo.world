#!/usr/bin/env python3
"""
Instagram Scrape Merger v2.0 - Arrow-first alignment with multiple algorithms.

PRIORITY: Arrow scrape (dates) is the BASE - every arrow entry appears in output.
Hover data is matched TO arrow data. Unmatched hover goes to orphans section.

Uses like counts as the alignment signal, similar to DNA sequence alignment.
Handles insertions/deletions (extra posts in one scrape but not the other).
"""

import pandas as pd
import os
from datetime import datetime
from collections import defaultdict

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

def arrow_first_match(hover_df, arrow_df, tolerance=0.15):
    """
    Arrow-first matching: Every arrow entry appears in output.
    Hover data is matched TO arrow. Returns (arrow_to_hover_map, orphan_hover_indices).
    """
    hover_likes = [normalize_likes(x) for x in hover_df['Likes'].tolist()]
    arrow_likes = [normalize_likes(x) for x in arrow_df['Likes'].tolist()]
    
    # Track which hover indices are used
    used_hover = set()
    arrow_to_hover = {}  # arrow_idx -> hover_idx
    
    # For each arrow entry, find best matching hover entry
    for a_idx, a_like in enumerate(arrow_likes):
        best_h_idx = None
        best_diff = float('inf')
        
        for h_idx, h_like in enumerate(hover_likes):
            if h_idx in used_hover:
                continue
            if likes_match(h_like, a_like, tolerance):
                if h_like is not None and a_like is not None:
                    diff = abs(h_like - a_like)
                else:
                    diff = 0
                if diff < best_diff:
                    best_diff = diff
                    best_h_idx = h_idx
        
        if best_h_idx is not None:
            arrow_to_hover[a_idx] = best_h_idx
            used_hover.add(best_h_idx)
    
    # Orphans are hover entries not matched
    orphan_hover = [i for i in range(len(hover_likes)) if i not in used_hover]
    
    return arrow_to_hover, orphan_hover

def sequential_arrow_first(hover_df, arrow_df, tolerance=0.20, max_skip=5):
    """
    Sequential arrow-first: Try to maintain order while matching.
    Allows skipping up to max_skip positions to find a match.
    """
    hover_likes = [normalize_likes(x) for x in hover_df['Likes'].tolist()]
    arrow_likes = [normalize_likes(x) for x in arrow_df['Likes'].tolist()]
    
    used_hover = set()
    arrow_to_hover = {}
    h_idx = 0  # Current position in hover
    
    for a_idx, a_like in enumerate(arrow_likes):
        # Try to find match starting from current hover position
        found = False
        for skip in range(max_skip + 1):
            test_h = h_idx + skip
            if test_h >= len(hover_likes):
                break
            if test_h in used_hover:
                continue
            
            h_like = hover_likes[test_h]
            if likes_match(h_like, a_like, tolerance):
                arrow_to_hover[a_idx] = test_h
                used_hover.add(test_h)
                h_idx = test_h + 1
                found = True
                break
        
        if not found:
            # Try looking backwards too
            for back in range(1, 3):
                test_h = h_idx - back
                if test_h >= 0 and test_h not in used_hover:
                    h_like = hover_likes[test_h]
                    if likes_match(h_like, a_like, tolerance):
                        arrow_to_hover[a_idx] = test_h
                        used_hover.add(test_h)
                        found = True
                        break
    
    orphan_hover = [i for i in range(len(hover_likes)) if i not in used_hover]
    return arrow_to_hover, orphan_hover

def dp_arrow_first(hover_df, arrow_df, tolerance=0.15):
    """
    Dynamic programming arrow-first alignment.
    Optimizes for maximum matches while respecting order.
    """
    hover_likes = [normalize_likes(x) for x in hover_df['Likes'].tolist()]
    arrow_likes = [normalize_likes(x) for x in arrow_df['Likes'].tolist()]
    
    n_hover = len(hover_likes)
    n_arrow = len(arrow_likes)
    
    # dp[a][h] = max matches using arrow[0:a] and hover[0:h]
    dp = [[0] * (n_hover + 1) for _ in range(n_arrow + 1)]
    
    for a in range(1, n_arrow + 1):
        for h in range(1, n_hover + 1):
            # Option 1: Don't use hover[h-1] for this arrow
            dp[a][h] = max(dp[a][h-1], dp[a-1][h])
            
            # Option 2: Match arrow[a-1] with hover[h-1] if they match
            if likes_match(arrow_likes[a-1], hover_likes[h-1], tolerance):
                dp[a][h] = max(dp[a][h], dp[a-1][h-1] + 1)
    
    # Traceback to find the actual matching
    arrow_to_hover = {}
    a, h = n_arrow, n_hover
    
    while a > 0 and h > 0:
        if likes_match(arrow_likes[a-1], hover_likes[h-1], tolerance) and dp[a][h] == dp[a-1][h-1] + 1:
            arrow_to_hover[a-1] = h-1
            a -= 1
            h -= 1
        elif dp[a][h] == dp[a][h-1]:
            h -= 1
        else:
            a -= 1
    
    used_hover = set(arrow_to_hover.values())
    orphan_hover = [i for i in range(n_hover) if i not in used_hover]
    
    return arrow_to_hover, orphan_hover

def multi_tolerance_match(hover_df, arrow_df):
    """
    Try multiple tolerance levels, starting strict and relaxing.
    Returns best result with ranking info.
    """
    tolerances = [0.05, 0.10, 0.15, 0.20, 0.30]
    results = []
    
    for tol in tolerances:
        arrow_to_hover, orphans = dp_arrow_first(hover_df, arrow_df, tolerance=tol)
        match_count = len(arrow_to_hover)
        results.append({
            'tolerance': tol,
            'matches': match_count,
            'orphans': len(orphans),
            'mapping': arrow_to_hover,
            'orphan_list': orphans
        })
    
    return results

def build_merged_df(hover_df, arrow_df, arrow_to_hover, orphan_hover):
    """
    Build the merged dataframe with arrow as base.
    Every arrow entry appears. Unmatched hover goes to orphans.
    """
    merged_rows = []
    
    # Process each arrow entry
    for a_idx in range(len(arrow_df)):
        a_row = arrow_df.iloc[a_idx]
        row = {
            'Arrow Pos': a_idx + 1,
            'Date': a_row.get('Date', ''),
            'Date (ISO)': a_row.get('Date (ISO)', ''),
            'Arrow Likes': a_row.get('Likes', ''),
        }
        
        if a_idx in arrow_to_hover:
            h_idx = arrow_to_hover[a_idx]
            h_row = hover_df.iloc[h_idx]
            row['Hover Pos'] = h_idx + 1
            row['Reel ID'] = h_row.get('Reel ID', '')
            row['Views'] = h_row.get('Views', '')
            row['Hover Likes'] = h_row.get('Likes', '')
            row['Comments'] = h_row.get('Comments', '')
            row['URL'] = h_row.get('URL', '')
            
            # Check match quality
            h_like = normalize_likes(row['Hover Likes'])
            a_like = normalize_likes(row['Arrow Likes'])
            if h_like and a_like:
                diff_pct = abs(h_like - a_like) / max(h_like, a_like) * 100
                row['Match'] = f"✓ ({diff_pct:.1f}%)"
            else:
                row['Match'] = '✓'
        else:
            row['Hover Pos'] = ''
            row['Reel ID'] = '[NO MATCH]'
            row['Views'] = ''
            row['Hover Likes'] = ''
            row['Comments'] = ''
            row['URL'] = ''
            row['Match'] = '✗'
        
        merged_rows.append(row)
    
    return pd.DataFrame(merged_rows)

def build_orphans_df(hover_df, orphan_indices):
    """Build dataframe for orphaned hover entries."""
    if not orphan_indices:
        return pd.DataFrame()
    
    orphan_rows = []
    for h_idx in orphan_indices:
        h_row = hover_df.iloc[h_idx]
        orphan_rows.append({
            'Hover Pos': h_idx + 1,
            'Reel ID': h_row.get('Reel ID', ''),
            'Views': h_row.get('Views', ''),
            'Likes': h_row.get('Likes', ''),
            'Comments': h_row.get('Comments', ''),
            'URL': h_row.get('URL', ''),
            'Status': 'No matching arrow date'
        })
    
    return pd.DataFrame(orphan_rows)

def merge_account_v2(hover_df, arrow_df, method='dp_arrow_first', tolerance=0.15):
    """
    Arrow-first merge with specified method.
    Returns merged_df, orphans_df, and stats.
    """
    hover_likes = [normalize_likes(x) for x in hover_df['Likes'].tolist()]
    arrow_likes = [normalize_likes(x) for x in arrow_df['Likes'].tolist()]
    
    print(f"    Hover: {len(hover_likes)} posts, Arrow: {len(arrow_likes)} posts")
    print(f"    Hover likes sample: {hover_likes[:5]}")
    print(f"    Arrow likes sample: {arrow_likes[:5]}")
    
    if method == 'dp_arrow_first':
        arrow_to_hover, orphans = dp_arrow_first(hover_df, arrow_df, tolerance)
        print(f"    DP Arrow-First: {len(arrow_to_hover)} matches, {len(orphans)} orphans")
    elif method == 'sequential':
        arrow_to_hover, orphans = sequential_arrow_first(hover_df, arrow_df, tolerance)
        print(f"    Sequential: {len(arrow_to_hover)} matches, {len(orphans)} orphans")
    elif method == 'greedy':
        arrow_to_hover, orphans = arrow_first_match(hover_df, arrow_df, tolerance)
        print(f"    Greedy: {len(arrow_to_hover)} matches, {len(orphans)} orphans")
    else:
        raise ValueError(f"Unknown method: {method}")
    
    merged_df = build_merged_df(hover_df, arrow_df, arrow_to_hover, orphans)
    orphans_df = build_orphans_df(hover_df, orphans)
    
    stats = {
        'total_arrow': len(arrow_df),
        'total_hover': len(hover_df),
        'matches': len(arrow_to_hover),
        'orphans': len(orphans),
        'match_rate': len(arrow_to_hover) / len(arrow_df) * 100 if len(arrow_df) > 0 else 0
    }
    
    return merged_df, orphans_df, stats

def run_all_methods_v2(hover_df, arrow_df):
    """Run all arrow-first methods with multiple tolerances and rank them."""
    methods = ['dp_arrow_first', 'sequential', 'greedy']
    tolerances = [0.10, 0.15, 0.20, 0.25]
    
    all_results = []
    
    for method in methods:
        for tol in tolerances:
            try:
                merged, orphans, stats = merge_account_v2(hover_df, arrow_df, method=method, tolerance=tol)
                all_results.append({
                    'method': method,
                    'tolerance': tol,
                    'matches': stats['matches'],
                    'orphans': stats['orphans'],
                    'match_rate': stats['match_rate'],
                    'merged': merged,
                    'orphans_df': orphans
                })
                print(f"    {method} (tol={tol:.0%}): {stats['matches']}/{stats['total_arrow']} matches ({stats['match_rate']:.1f}%), {stats['orphans']} orphans")
            except Exception as e:
                print(f"    {method} (tol={tol:.0%}): ERROR - {e}")
    
    # Rank by matches (primary), then by fewer orphans (secondary)
    all_results.sort(key=lambda x: (-x['matches'], x['orphans']))
    
    print(f"\n  📊 RANKING:")
    for i, r in enumerate(all_results[:5], 1):
        print(f"    #{i}: {r['method']} (tol={r['tolerance']:.0%}) - {r['matches']} matches, {r['orphans']} orphans")
    
    best = all_results[0] if all_results else None
    if best:
        print(f"\n  🏆 BEST: {best['method']} (tol={best['tolerance']:.0%}) with {best['matches']} matches")
    
    return all_results, best

def main():
    print("="*70)
    print("📊 Instagram Scrape Merger v2.0 (Arrow-First)")
    print("="*70)
    print("Priority: Every arrow (date) entry appears in output")
    print("Hover data matched TO arrow. Unmatched hover = orphans.")
    
    # Check files exist
    if not os.path.exists(HOVER_FILE):
        print(f"❌ Hover file not found: {HOVER_FILE}")
        return
    if not os.path.exists(ARROW_FILE):
        print(f"❌ Arrow file not found: {ARROW_FILE}")
        return
    
    print(f"\n📁 Loading {HOVER_FILE} and {ARROW_FILE}...")
    accounts = load_scrape_data(HOVER_FILE, ARROW_FILE)
    print(f"✅ Found {len(accounts)} account(s)")
    
    # Ask for method
    print("\n🔧 Alignment methods available:")
    print("  1. DP Arrow-First (dynamic programming, respects order)")
    print("  2. Sequential (follows order with skip allowance)")
    print("  3. Greedy (best match per arrow, any order)")
    print("  4. Try ALL methods + tolerances, pick best (RECOMMENDED)")
    
    choice = input("\nSelect method (1-4, default=4): ").strip()
    
    methods_map = {
        '1': 'dp_arrow_first',
        '2': 'sequential', 
        '3': 'greedy',
        '4': 'all'
    }
    method = methods_map.get(choice, 'all')
    
    # Ask for tolerance if not running all
    if method != 'all':
        tol_input = input("Tolerance % (5-30, default=15): ").strip()
        try:
            tolerance = int(tol_input) / 100
        except:
            tolerance = 0.15
    else:
        tolerance = 0.15
    
    # Process each account
    all_merged = {}
    all_orphans = {}
    
    for account, data in accounts.items():
        print(f"\n{'='*70}")
        print(f"📱 Processing {account}")
        print("="*70)
        
        hover_df = data['hover']
        arrow_df = data['arrow']
        
        if method == 'all':
            results, best = run_all_methods_v2(hover_df, arrow_df)
            if best:
                all_merged[account] = best['merged']
                all_orphans[account] = best['orphans_df']
        else:
            merged, orphans, stats = merge_account_v2(hover_df, arrow_df, method=method, tolerance=tolerance)
            all_merged[account] = merged
            all_orphans[account] = orphans
            print(f"\n  Match rate: {stats['match_rate']:.1f}%")
    
    # Save results
    if not all_merged:
        print("❌ No data to save - no accounts were processed successfully")
        return
    
    print(f"\n💾 Saving to {OUTPUT_FILE}...")
    try:
        with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
            for account in all_merged:
                # Main merged data - sanitize sheet name
                sheet_name = account.replace('@', '').replace('/', '_')[:31]
                if not sheet_name:
                    sheet_name = "Account"
                
                merged_df = all_merged[account]
                if merged_df is None or len(merged_df) == 0:
                    print(f"  ⚠️ Skipping {account} - no merged data")
                    continue
                    
                merged_df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"  ✓ Wrote {sheet_name}: {len(merged_df)} rows")
                
                # Orphans sheet if any
                if account in all_orphans and all_orphans[account] is not None and len(all_orphans[account]) > 0:
                    orphan_sheet = f"{sheet_name[:26]}_orph"
                    all_orphans[account].to_excel(writer, sheet_name=orphan_sheet, index=False)
                    print(f"  ✓ Wrote {orphan_sheet}: {len(all_orphans[account])} orphans")
        
        print(f"\n✅ Merged data saved to {OUTPUT_FILE}")
        print("\nSheets created:")
        for account in all_merged:
            sheet_name = account.replace('@', '').replace('/', '_')[:31]
            if all_merged[account] is not None and len(all_merged[account]) > 0:
                print(f"  - {sheet_name}: {len(all_merged[account])} rows")
                if account in all_orphans and all_orphans[account] is not None and len(all_orphans[account]) > 0:
                    print(f"  - {sheet_name[:26]}_orph: {len(all_orphans[account])} orphaned hover entries")
    except PermissionError:
        print(f"❌ Cannot save - {OUTPUT_FILE} is open in another program. Close Excel and try again.")
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        import traceback
        traceback.print_exc()
    
    print("="*70)

if __name__ == "__main__":
    main()
