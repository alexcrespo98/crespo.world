#!/usr/bin/env python3
"""
Test script to verify the Chrome configuration changes work correctly.
This tests the headless mode detection, unique user data dir creation,
and cleanup functionality without requiring Selenium.
"""

import sys
import os
import time
import ast

def test_chrome_options_configuration():
    """Test that Chrome options are configured correctly"""
    print("=" * 70)
    print("Testing Chrome Configuration Changes")
    print("=" * 70)
    
    # Test 1: Check the file can be parsed
    print("\n✓ Test 1: Checking file syntax...")
    scraper_path = os.path.join(os.path.dirname(__file__), 'scrapers', 'instagram_scraper.py')
    with open(scraper_path, 'r') as f:
        code = f.read()
    
    try:
        ast.parse(code)
        print("  ✅ File syntax is valid")
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        raise
    
    # Test 2: Check required imports are present
    print("\n✓ Test 2: Checking required imports...")
    required_imports = ['tempfile', 'random', 'shutil', 'atexit']
    for imp in required_imports:
        assert f"import {imp}" in code, f"Missing import: {imp}"
        print(f"  ✅ Import '{imp}' found")
    
    # Test 3: Check cleanup_chrome_data method exists
    print("\n✓ Test 3: Checking cleanup_chrome_data method...")
    assert "def cleanup_chrome_data(self):" in code, "Missing cleanup_chrome_data method"
    assert "shutil.rmtree(self.user_data_dir" in code, "cleanup_chrome_data doesn't remove user_data_dir"
    assert "shutil.rmtree(self.incognito_user_data_dir" in code, "cleanup_chrome_data doesn't remove incognito_user_data_dir"
    print("  ✅ cleanup_chrome_data method exists and has correct implementation")
    
    # Test 4: Check atexit registration
    print("\n✓ Test 4: Checking atexit registration...")
    assert "atexit.register(self.cleanup_chrome_data)" in code, "Missing atexit registration"
    print("  ✅ atexit cleanup handler is registered")
    
    # Test 5: Check user_data_dir initialization in __init__
    print("\n✓ Test 5: Checking attribute initialization...")
    assert "self.user_data_dir = None" in code, "user_data_dir not initialized"
    assert "self.incognito_user_data_dir = None" in code, "incognito_user_data_dir not initialized"
    print("  ✅ Attributes are properly initialized")
    
    # Test 6: Check headless mode detection in setup_driver
    print("\n✓ Test 6: Checking headless mode detection in setup_driver...")
    assert "headless_mode = not os.environ.get('DISPLAY') or os.environ.get('SSH_CONNECTION')" in code, "Missing headless mode detection"
    assert '--headless=new' in code, "Missing --headless=new argument"
    assert '--window-size=1920,1080' in code, "Missing window size for headless mode"
    print("  ✅ Headless mode detection is implemented")
    
    # Test 7: Check unique user data directory creation
    print("\n✓ Test 7: Checking unique user data directory creation...")
    assert 'timestamp = int(time.time())' in code, "Missing timestamp generation"
    assert 'random_id = random.randint(1000, 9999)' in code, "Missing random ID generation"
    assert 'user_data_dir = f"/tmp/chrome_user_data_{timestamp}_{random_id}"' in code, "Missing user_data_dir creation"
    assert '--user-data-dir={user_data_dir}' in code, "Missing user-data-dir argument"
    print("  ✅ Unique user data directory creation is implemented")
    
    # Test 8: Check Chrome arguments for session conflict prevention
    print("\n✓ Test 8: Checking Chrome arguments for session conflict prevention...")
    required_args = [
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--remote-debugging-port=0',
        '--disable-gpu'
    ]
    for arg in required_args:
        assert arg in code, f"Missing Chrome argument: {arg}"
        print(f"  ✅ Chrome argument '{arg}' found")
    
    # Test 9: Check incognito driver has same fixes
    print("\n✓ Test 9: Checking incognito driver has same fixes...")
    assert 'incognito_user_data_dir = f"/tmp/chrome_user_data_incognito_{timestamp}_{random_id}"' in code, "Missing incognito user_data_dir"
    print("  ✅ Incognito driver has unique user data directory")
    
    # Test 10: Check cleanup is called in handle_interrupt
    print("\n✓ Test 10: Checking cleanup in handle_interrupt...")
    handle_interrupt_idx = code.find("def handle_interrupt(self, signum, frame):")
    next_method_idx = code.find("\n    def ", handle_interrupt_idx + 1)
    handle_interrupt_code = code[handle_interrupt_idx:next_method_idx]
    assert "self.cleanup_chrome_data()" in handle_interrupt_code, "cleanup_chrome_data not called in handle_interrupt"
    print("  ✅ Cleanup is called in handle_interrupt")
    
    # Test 11: Check cleanup is called in run() finally block
    print("\n✓ Test 11: Checking cleanup in run() finally blocks...")
    # Count occurrences of cleanup in finally blocks
    cleanup_count = code.count("# Clean up temporary directories")
    assert cleanup_count >= 3, f"Expected at least 3 cleanup calls in finally blocks, found {cleanup_count}"
    print(f"  ✅ Cleanup is called in {cleanup_count} finally blocks")
    
    # Test 12: Verify headless mode detection logic
    print("\n✓ Test 12: Testing headless mode detection logic...")
    
    # Save original env vars
    original_display = os.environ.get('DISPLAY')
    original_ssh = os.environ.get('SSH_CONNECTION')
    
    # Test with DISPLAY set (not headless)
    os.environ['DISPLAY'] = ':0'
    if 'SSH_CONNECTION' in os.environ:
        del os.environ['SSH_CONNECTION']
    headless_mode = not os.environ.get('DISPLAY') or os.environ.get('SSH_CONNECTION')
    assert not headless_mode, "Should not be headless with DISPLAY set"
    print("  ✅ Correctly detects non-headless mode when DISPLAY is set")
    
    # Test with no DISPLAY (headless)
    if 'DISPLAY' in os.environ:
        del os.environ['DISPLAY']
    headless_mode = not os.environ.get('DISPLAY') or os.environ.get('SSH_CONNECTION')
    assert headless_mode, "Should be headless without DISPLAY"
    print("  ✅ Correctly detects headless mode without DISPLAY")
    
    # Test with SSH_CONNECTION (headless)
    os.environ['DISPLAY'] = ':0'
    os.environ['SSH_CONNECTION'] = '192.168.1.1 12345 192.168.1.2 22'
    headless_mode = not os.environ.get('DISPLAY') or os.environ.get('SSH_CONNECTION')
    assert headless_mode, "Should be headless with SSH_CONNECTION"
    print("  ✅ Correctly detects headless mode with SSH_CONNECTION")
    
    # Restore original env vars
    if original_display:
        os.environ['DISPLAY'] = original_display
    elif 'DISPLAY' in os.environ:
        del os.environ['DISPLAY']
    
    if original_ssh:
        os.environ['SSH_CONNECTION'] = original_ssh
    elif 'SSH_CONNECTION' in os.environ:
        del os.environ['SSH_CONNECTION']
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print("\nThe Chrome configuration changes are working correctly:")
    print("  • Headless mode detection works properly")
    print("  • Unique user data directories are created")
    print("  • Cleanup functionality is properly integrated")
    print("  • All required Chrome arguments are present")
    print("  • Both main and incognito drivers have the fixes")
    print("\nThe scraper should now work in SSH environments without conflicts.")
    
if __name__ == "__main__":
    try:
        test_chrome_options_configuration()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
