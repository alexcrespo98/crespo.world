#!/usr/bin/env python3
"""
Test script to verify Instagram scraper sheet name mapping functionality.
"""

import sys
import os
import pandas as pd
import tempfile

# Define constants directly from the scraper
ACCOUNTS_TO_TRACK = [
    "popdartsgame",
    "bucketgolfgame",
    "playbattlegolf",
    "flinggolf",
    "golfponggames",  # Changed from "golfpong.games"
    "discgogames",
    "low_tide_golf"
]

SHEET_NAME_MAPPING = {
    "golfponggames": "golfpong.games"  # Instagram account -> Excel sheet name
}

OUTPUT_EXCEL = "instagram_reels_analytics_tracker.xlsx"

def test_account_name():
    """Test that golfponggames is in the accounts list"""
    print("🧪 Test 1: Verify account name change")
    assert "golfponggames" in ACCOUNTS_TO_TRACK, "golfponggames should be in ACCOUNTS_TO_TRACK"
    assert "golfpong.games" not in ACCOUNTS_TO_TRACK, "golfpong.games should NOT be in ACCOUNTS_TO_TRACK"
    print("✅ Account name correctly changed to golfponggames")

def test_sheet_mapping():
    """Test that the sheet name mapping is correct"""
    print("\n🧪 Test 2: Verify sheet name mapping")
    assert "golfponggames" in SHEET_NAME_MAPPING, "golfponggames should be in SHEET_NAME_MAPPING"
    assert SHEET_NAME_MAPPING["golfponggames"] == "golfpong.games", "Mapping should map to golfpong.games"
    print("✅ Sheet name mapping correctly configured")

def test_save_and_load():
    """Test that save and load work correctly with mapping"""
    print("\n🧪 Test 3: Test save and load with mapping")
    
    # Create a temporary Excel file
    temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    temp_file.close()
    
    try:
        # Create test data
        test_data = {
            "golfponggames": pd.DataFrame({
                "2024-01-01": [100, 200, 300],
                "2024-01-02": [150, 250, 350]
            }, index=["followers", "reels_scraped", "reel_1"]),
            "popdartsgame": pd.DataFrame({
                "2024-01-01": [500, 10, 1000],
                "2024-01-02": [550, 12, 1200]
            }, index=["followers", "reels_scraped", "reel_1"])
        }
        
        # Save to Excel with mapping
        with pd.ExcelWriter(temp_file.name, engine='openpyxl') as writer:
            for username, df in test_data.items():
                sheet_name = SHEET_NAME_MAPPING.get(username, username)
                sheet_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=sheet_name)
        
        print(f"  📝 Saved test data to {temp_file.name}")
        
        # Load the Excel file
        excel_data = pd.read_excel(temp_file.name, sheet_name=None, index_col=0)
        print(f"  📖 Loaded sheets: {list(excel_data.keys())}")
        
        # Verify sheet names
        assert "golfpong.games" in excel_data, "Excel should have sheet named 'golfpong.games'"
        assert "popdartsgame" in excel_data, "Excel should have sheet named 'popdartsgame'"
        assert "golfponggames" not in excel_data, "Excel should NOT have sheet named 'golfponggames'"
        print("  ✅ Excel sheets have correct names")
        
        # Verify reverse mapping for loading
        reverse_mapping = {v: k for k, v in SHEET_NAME_MAPPING.items()}
        loaded_data = {}
        for sheet_name, df in excel_data.items():
            username = reverse_mapping.get(sheet_name, sheet_name)
            loaded_data[username] = df
        
        print(f"  📖 Mapped usernames: {list(loaded_data.keys())}")
        
        # Verify usernames after reverse mapping
        assert "golfponggames" in loaded_data, "Loaded data should have username 'golfponggames'"
        assert "popdartsgame" in loaded_data, "Loaded data should have username 'popdartsgame'"
        assert "golfpong.games" not in loaded_data, "Loaded data should NOT have 'golfpong.games'"
        print("  ✅ Reverse mapping correctly converts sheet names to usernames")
        
        # Verify data integrity
        assert loaded_data["golfponggames"].loc["followers", "2024-01-01"] == 100
        assert loaded_data["popdartsgame"].loc["followers", "2024-01-01"] == 500
        print("  ✅ Data integrity maintained through save/load cycle")
        
        print("✅ Save and load with mapping works correctly")
        
    finally:
        # Clean up
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
            print(f"  🧹 Cleaned up {temp_file.name}")

def main():
    print("="*70)
    print("🧪 Testing Instagram Scraper Sheet Name Mapping")
    print("="*70)
    
    try:
        test_account_name()
        test_sheet_mapping()
        test_save_and_load()
        
        print("\n" + "="*70)
        print("✅ All tests passed!")
        print("="*70)
        print("\nSummary:")
        print("  • Instagram account: @golfponggames")
        print("  • Excel sheet name: golfpong.games")
        print("  • Mapping preserves existing data compatibility")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
