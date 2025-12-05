#!/usr/bin/env python3
"""
YouTube Live Subscriber Count Extraction Test Script

This script tests various methods to extract the exact/real-time subscriber count
from livecounts.io for a given YouTube channel.

The challenge: livecounts.io initially shows an approximate count, then updates
to the exact count after a short delay. This script tries multiple approaches
to capture the real value.

Methods tested:
1. Initial page load value
2. Waiting for DOM value updates (polling)
3. Monitoring DOM changes with intervals
4. Intercepting network/XHR requests for API data
5. Waiting for specific element state changes

Usage:
    python youtube_livecounts_test.py
"""

import sys
import subprocess
import os
import time
import re
import json
from datetime import datetime


def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])


def ensure_packages():
    """Ensure required packages are installed"""
    packages_needed = []
    required = {
        'selenium': 'selenium',
        'webdriver_manager': 'webdriver-manager',
        'requests': 'requests'
    }
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            packages_needed.append(package)
    if packages_needed:
        print("📦 Installing required packages...")
        for p in packages_needed:
            install_package(p)
        print("✅ All packages installed!")


def setup_driver(browser='chrome', headless=False):
    """Set up browser driver"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    
    print(f"  🌐 Setting up {'headless ' if headless else ''}Chrome driver...")
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-logging")
    
    if headless:
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
    
    # Enable performance logging to capture network requests
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    service = ChromeService(ChromeDriverManager().install())
    service.log_path = os.devnull
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver


def parse_subscriber_count(text):
    """
    Parse subscriber count from text, handling abbreviations like K, M, B
    and also handling full numbers with commas.
    
    Returns: int or None
    """
    if not text:
        return None
    
    text = str(text).strip().upper().replace(',', '').replace(' ', '')
    
    # Try to match number with optional suffix
    match = re.match(r'^([\d.]+)([KMB]?)$', text)
    if match:
        number_str, suffix = match.groups()
        try:
            number = float(number_str)
            multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000, '': 1}
            if suffix in multipliers:
                return int(number * multipliers[suffix])
        except ValueError:
            pass
    
    # Try to parse as direct integer
    try:
        return int(text)
    except ValueError:
        pass
    
    return None


def method_1_initial_load(driver, url, results):
    """
    Method 1: Simple page load and immediate extraction
    """
    print("\n" + "="*60)
    print("📋 METHOD 1: Initial Page Load (immediate extraction)")
    print("="*60)
    
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    try:
        driver.get(url)
        time.sleep(2)  # Brief wait for page to load
        
        # Look for subscriber count element
        count_selectors = [
            "div.odometer-inside",
            "span.odometer-value",
            "div[class*='odometer']",
            "span[class*='count']",
            "div[class*='count']",
            "#count",
        ]
        
        for selector in count_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for elem in elements:
                        text = elem.text.strip()
                        if text:
                            count = parse_subscriber_count(text)
                            print(f"  Found element ({selector}): '{text}' → {count if count else 'N/A'}")
                            if count:
                                results['method_1_initial'] = {
                                    'selector': selector,
                                    'raw_text': text,
                                    'count': count,
                                    'timestamp': datetime.now().isoformat()
                                }
            except:
                continue
        
        # Also try to get any large number visible on page
        body_text = driver.find_element(By.TAG_NAME, "body").text
        numbers = re.findall(r'\b\d[\d,]+\d\b', body_text)
        if numbers:
            print(f"  Large numbers found on page: {numbers[:5]}")
            for num_str in numbers[:5]:
                num = parse_subscriber_count(num_str)
                if num and num > 1000:  # Likely subscriber count
                    if 'method_1_initial' not in results:
                        results['method_1_initial'] = {
                            'selector': 'body_text_regex',
                            'raw_text': num_str,
                            'count': num,
                            'timestamp': datetime.now().isoformat()
                        }
                    break
        
        if 'method_1_initial' not in results:
            print("  ❌ No subscriber count found with initial load")
            results['method_1_initial'] = {'error': 'No count found'}
        else:
            print(f"  ✅ Initial count: {results['method_1_initial'].get('count', 'N/A')}")
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        results['method_1_initial'] = {'error': str(e)}


def method_2_wait_for_updates(driver, url, results, wait_seconds=15):
    """
    Method 2: Wait and poll for value updates
    Records values over time to detect when the "real" value appears
    """
    print("\n" + "="*60)
    print(f"📋 METHOD 2: Polling for Updates ({wait_seconds}s)")
    print("="*60)
    
    from selenium.webdriver.common.by import By
    
    try:
        driver.get(url)
        time.sleep(2)
        
        observed_values = []
        
        start_time = time.time()
        poll_interval = 0.5  # Poll every 500ms
        
        while time.time() - start_time < wait_seconds:
            # Try to extract current value
            try:
                # Look for odometer elements (common on livecounts.io)
                odometer_parts = driver.find_elements(By.CSS_SELECTOR, ".odometer-inside .odometer-digit .odometer-value")
                if odometer_parts:
                    # Concatenate all digit values
                    digits = [part.text for part in odometer_parts if part.text.isdigit()]
                    if digits:
                        count_str = ''.join(digits)
                        count = int(count_str) if count_str else None
                        elapsed = round(time.time() - start_time, 1)
                        observed_values.append({
                            'time': elapsed,
                            'count': count,
                            'raw': count_str
                        })
                        print(f"  [{elapsed}s] Count: {count}")
                else:
                    # Fallback: look for any element with class containing 'count'
                    count_elem = driver.find_elements(By.CSS_SELECTOR, "[class*='count']")
                    if count_elem:
                        text = count_elem[0].text.strip()
                        count = parse_subscriber_count(text)
                        if count:
                            elapsed = round(time.time() - start_time, 1)
                            observed_values.append({
                                'time': elapsed,
                                'count': count,
                                'raw': text
                            })
                            print(f"  [{elapsed}s] Count: {count} (from: '{text}')")
            except:
                pass
            
            time.sleep(poll_interval)
        
        if observed_values:
            # Find unique values in order of appearance
            unique_values = []
            seen = set()
            for v in observed_values:
                if v['count'] and v['count'] not in seen:
                    unique_values.append(v)
                    seen.add(v['count'])
            
            print(f"\n  📊 Observed {len(unique_values)} unique values:")
            for v in unique_values:
                print(f"     - {v['count']} (first seen at {v['time']}s)")
            
            # The last value is likely the "real" count
            final_value = observed_values[-1] if observed_values else None
            results['method_2_polling'] = {
                'unique_values': unique_values,
                'final_value': final_value,
                'total_observations': len(observed_values),
                'timestamp': datetime.now().isoformat()
            }
            print(f"\n  ✅ Final value: {final_value['count'] if final_value else 'N/A'}")
        else:
            print("  ❌ No values observed during polling")
            results['method_2_polling'] = {'error': 'No values observed'}
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        results['method_2_polling'] = {'error': str(e)}


def method_3_network_interception(driver, url, results):
    """
    Method 3: Intercept network requests to find API responses with subscriber data
    """
    print("\n" + "="*60)
    print("📋 METHOD 3: Network/XHR Request Interception")
    print("="*60)
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for API calls to complete
        
        # Get performance logs (network requests)
        logs = driver.get_log('performance')
        
        api_responses = []
        
        for log in logs:
            try:
                message = json.loads(log['message'])
                msg = message.get('message', {})
                
                # Look for network response events
                if msg.get('method') == 'Network.responseReceived':
                    response = msg.get('params', {}).get('response', {})
                    url_str = response.get('url', '')
                    
                    # Look for API endpoints that might contain subscriber data
                    if any(keyword in url_str.lower() for keyword in ['api', 'subscriber', 'count', 'channel', 'stats']):
                        api_responses.append({
                            'url': url_str,
                            'status': response.get('status'),
                            'mimeType': response.get('mimeType')
                        })
                        print(f"  Found API call: {url_str[:80]}...")
                
                # Also look for webSocket messages
                if msg.get('method') == 'Network.webSocketFrameReceived':
                    payload = msg.get('params', {}).get('response', {}).get('payloadData', '')
                    if payload:
                        # Try to parse as JSON and find subscriber count
                        try:
                            data = json.loads(payload)
                            if isinstance(data, dict):
                                for key in ['subscribers', 'subscriberCount', 'count', 'value']:
                                    if key in data:
                                        count = data[key]
                                        if isinstance(count, (int, float)) and count > 1000:
                                            print(f"  Found WebSocket data: {key} = {count}")
                                            api_responses.append({
                                                'type': 'websocket',
                                                'key': key,
                                                'count': int(count)
                                            })
                        except:
                            pass
                            
            except Exception as e:
                continue
        
        if api_responses:
            results['method_3_network'] = {
                'api_calls_found': len(api_responses),
                'responses': api_responses[:10],  # Limit to first 10
                'timestamp': datetime.now().isoformat()
            }
            print(f"\n  ✅ Found {len(api_responses)} potential API responses")
        else:
            print("  ⚠️ No relevant API calls intercepted")
            results['method_3_network'] = {'error': 'No API calls found', 'note': 'LiveCounts may use WebSockets or obfuscated endpoints'}
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        results['method_3_network'] = {'error': str(e)}


def method_4_wait_for_stable_value(driver, url, results, stability_threshold=3, max_wait=20):
    """
    Method 4: Wait until the value stabilizes (stops changing)
    This helps detect when the page has loaded the "real" value
    """
    print("\n" + "="*60)
    print(f"📋 METHOD 4: Wait for Stable Value (threshold: {stability_threshold}s)")
    print("="*60)
    
    from selenium.webdriver.common.by import By
    
    try:
        driver.get(url)
        time.sleep(2)
        
        last_value = None
        stable_since = None
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            current_value = None
            
            try:
                # Try multiple selectors
                selectors = [
                    ".odometer-inside",
                    "[class*='odometer']",
                    "[class*='count']",
                    "#count"
                ]
                
                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        text = elements[0].text.strip().replace(' ', '').replace(',', '')
                        # Try to extract just digits
                        digits = ''.join(c for c in text if c.isdigit())
                        if digits:
                            current_value = int(digits)
                            break
            except:
                pass
            
            if current_value:
                elapsed = round(time.time() - start_time, 1)
                
                if current_value == last_value:
                    if stable_since is None:
                        stable_since = time.time()
                    
                    stability_duration = time.time() - stable_since
                    if stability_duration >= stability_threshold:
                        print(f"  ✅ Value stabilized at {current_value} after {elapsed}s")
                        results['method_4_stable'] = {
                            'count': current_value,
                            'stabilized_at': elapsed,
                            'stability_duration': round(stability_duration, 1),
                            'timestamp': datetime.now().isoformat()
                        }
                        return
                else:
                    if last_value is not None:
                        print(f"  [{elapsed}s] Value changed: {last_value} → {current_value}")
                    stable_since = None
                    last_value = current_value
            
            time.sleep(0.5)
        
        print(f"  ⚠️ Max wait time reached. Last value: {last_value}")
        results['method_4_stable'] = {
            'count': last_value,
            'stabilized': False,
            'note': 'Max wait time reached',
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        results['method_4_stable'] = {'error': str(e)}


def method_5_javascript_extraction(driver, url, results):
    """
    Method 5: Use JavaScript to directly access the page's internal state/variables
    """
    print("\n" + "="*60)
    print("📋 METHOD 5: JavaScript Variable Extraction")
    print("="*60)
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for page to fully load
        
        js_results = {}
        
        # Try to access common variable names where the count might be stored
        js_checks = [
            "typeof subscriberCount !== 'undefined' ? subscriberCount : null",
            "typeof count !== 'undefined' ? count : null",
            "typeof currentCount !== 'undefined' ? currentCount : null",
            "typeof liveCount !== 'undefined' ? liveCount : null",
            "typeof window.subscriberCount !== 'undefined' ? window.subscriberCount : null",
            "typeof window.count !== 'undefined' ? window.count : null",
            # Try to get from odometer element
            "document.querySelector('.odometer-inside') ? document.querySelector('.odometer-inside').innerText.replace(/[^0-9]/g, '') : null",
            "document.querySelector('[class*=\"odometer\"]') ? document.querySelector('[class*=\"odometer\"]').innerText.replace(/[^0-9]/g, '') : null",
        ]
        
        for js_code in js_checks:
            try:
                result = driver.execute_script(f"return {js_code}")
                if result:
                    print(f"  Found: {js_code[:50]}... = {result}")
                    if isinstance(result, str):
                        result = int(result) if result.isdigit() else result
                    js_results[js_code[:30]] = result
            except:
                continue
        
        # Try to get React/Vue state if available
        try:
            react_state = driver.execute_script("""
                const root = document.querySelector('#root') || document.querySelector('#app');
                if (root && root._reactRootContainer) {
                    return JSON.stringify(root._reactRootContainer._internalRoot.current.memoizedState);
                }
                return null;
            """)
            if react_state:
                print(f"  Found React state (partial): {react_state[:100]}...")
                js_results['react_state'] = 'found'
        except:
            pass
        
        if js_results:
            results['method_5_javascript'] = {
                'variables_found': js_results,
                'timestamp': datetime.now().isoformat()
            }
            print(f"\n  ✅ Found {len(js_results)} JavaScript values")
        else:
            print("  ⚠️ No JavaScript variables found with subscriber count")
            results['method_5_javascript'] = {'error': 'No variables found'}
            
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        results['method_5_javascript'] = {'error': str(e)}


def method_6_multiple_page_loads(driver, url, results, num_loads=3):
    """
    Method 6: Load the page multiple times and compare results
    to identify if there's a pattern in how the real value appears
    """
    print("\n" + "="*60)
    print(f"📋 METHOD 6: Multiple Page Loads (x{num_loads})")
    print("="*60)
    
    from selenium.webdriver.common.by import By
    
    load_results = []
    
    for i in range(num_loads):
        print(f"\n  --- Load {i+1}/{num_loads} ---")
        
        try:
            driver.get(url)
            
            values_over_time = []
            
            # Capture values at different time points
            time_points = [0.5, 1, 2, 3, 5, 8, 10]
            start = time.time()
            
            for t in time_points:
                wait_until = start + t
                current_wait = wait_until - time.time()
                if current_wait > 0:
                    time.sleep(current_wait)
                
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, ".odometer-inside, [class*='odometer'], [class*='count']")
                    if elements:
                        text = elements[0].text.strip().replace(' ', '').replace(',', '')
                        digits = ''.join(c for c in text if c.isdigit())
                        if digits:
                            count = int(digits)
                            values_over_time.append({'time': t, 'count': count})
                            print(f"    [{t}s] {count}")
                except:
                    pass
            
            if values_over_time:
                load_results.append({
                    'load_number': i + 1,
                    'values': values_over_time,
                    'final_value': values_over_time[-1]['count'] if values_over_time else None
                })
                
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            load_results.append({'load_number': i + 1, 'error': str(e)})
    
    # Analyze results
    final_values = [r['final_value'] for r in load_results if r.get('final_value')]
    
    if final_values:
        # Check if values are consistent
        unique_finals = list(set(final_values))
        
        print(f"\n  📊 Final values across loads: {final_values}")
        print(f"  📊 Unique final values: {unique_finals}")
        
        # Use most common value as "best guess"
        from collections import Counter
        most_common = Counter(final_values).most_common(1)[0][0]
        
        results['method_6_multiple_loads'] = {
            'load_results': load_results,
            'final_values': final_values,
            'unique_values': unique_finals,
            'most_common': most_common,
            'consistent': len(unique_finals) == 1,
            'timestamp': datetime.now().isoformat()
        }
        print(f"\n  ✅ Most common final value: {most_common}")
    else:
        results['method_6_multiple_loads'] = {'error': 'No values captured'}


def run_all_methods(channel_id, headless=False):
    """
    Run all methods to extract subscriber count and compare results
    """
    ensure_packages()
    
    url = f"https://livecounts.io/youtube-live-subscriber-counter/{channel_id}"
    
    print("\n" + "="*70)
    print("🔬 YouTube Live Subscriber Count Extraction Test")
    print("="*70)
    print(f"\n📺 Channel ID: {channel_id}")
    print(f"🌐 URL: {url}")
    print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'channel_id': channel_id,
        'url': url,
        'start_time': datetime.now().isoformat()
    }
    
    driver = None
    
    try:
        driver = setup_driver(headless=headless)
        
        # Run all methods
        method_1_initial_load(driver, url, results)
        method_2_wait_for_updates(driver, url, results)
        method_3_network_interception(driver, url, results)
        method_4_wait_for_stable_value(driver, url, results)
        method_5_javascript_extraction(driver, url, results)
        method_6_multiple_page_loads(driver, url, results)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        results['fatal_error'] = str(e)
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    results['end_time'] = datetime.now().isoformat()
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY OF ALL METHODS")
    print("="*70)
    
    all_counts = []
    
    for method_key in ['method_1_initial', 'method_2_polling', 'method_4_stable', 'method_5_javascript', 'method_6_multiple_loads']:
        if method_key in results and isinstance(results[method_key], dict):
            method_data = results[method_key]
            count = None
            
            if 'count' in method_data:
                count = method_data['count']
            elif 'final_value' in method_data and isinstance(method_data['final_value'], dict):
                count = method_data['final_value'].get('count')
            elif 'most_common' in method_data:
                count = method_data['most_common']
            elif 'variables_found' in method_data:
                for v in method_data['variables_found'].values():
                    if isinstance(v, int) and v > 1000:
                        count = v
                        break
            
            if count:
                all_counts.append(count)
                print(f"  {method_key}: {count:,}")
            elif 'error' in method_data:
                print(f"  {method_key}: ❌ {method_data['error']}")
    
    if all_counts:
        from collections import Counter
        most_common = Counter(all_counts).most_common(1)[0][0]
        print(f"\n🏆 BEST ESTIMATE: {most_common:,}")
        print(f"   (appeared {Counter(all_counts)[most_common]} times across methods)")
        results['best_estimate'] = most_common
    
    # Save results to file
    output_file = f"livecounts_test_{channel_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {output_file}")
    except Exception as e:
        print(f"\n⚠️ Could not save results to file: {e}")
    
    return results


def main():
    print("\n" + "="*70)
    print("🔬 YouTube Live Subscriber Count Extraction Test")
    print("="*70)
    
    # Default channel ID (popdartsgame)
    default_channel_id = "UCo4RsSblLnfBG5IuHJsvj4g"
    
    print(f"\nDefault channel ID: {default_channel_id}")
    channel_input = input("Enter channel ID (or press Enter for default): ").strip()
    
    if channel_input:
        channel_id = channel_input
    else:
        channel_id = default_channel_id
    
    # Ask about headless mode
    headless_choice = input("\nRun in headless mode? (y/n, default=n): ").strip().lower()
    headless = headless_choice == 'y'
    
    results = run_all_methods(channel_id, headless=headless)
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70)
    print("\nReview the results above to determine which method(s) work best")
    print("for extracting the exact subscriber count from livecounts.io")
    print("\nThe best approach will be implemented in youtube_scrape.py")


if __name__ == "__main__":
    main()
