#!/usr/bin/env python3
"""
Test script for recipeasy API authentication and functionality
"""

import requests
import json

# Test configuration
BASE_URL = "http://localhost:5000"
TEST_API_KEY = "test-key-12345"  # Will use for testing

def test_health_endpoint():
    """Test that /health endpoint is publicly accessible"""
    print("\n=== Testing /health endpoint (no auth required) ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200, "Health check failed"
    print("✓ Health endpoint works without authentication")

def test_simplify_no_auth():
    """Test that /simplify endpoint requires authentication"""
    print("\n=== Testing /simplify without API key ===")
    response = requests.post(
        f"{BASE_URL}/simplify",
        json={"input": "chocolate chip cookies"},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 401, "Should return 401 without API key"
    print("✓ Correctly returns 401 without API key")

def test_simplify_wrong_auth():
    """Test that /simplify endpoint rejects wrong API key"""
    print("\n=== Testing /simplify with wrong API key ===")
    response = requests.post(
        f"{BASE_URL}/simplify",
        json={"input": "chocolate chip cookies"},
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer wrong-key"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 401, "Should return 401 with wrong API key"
    print("✓ Correctly returns 401 with wrong API key")

def test_simplify_with_auth_url():
    """Test /simplify with correct API key and URL input"""
    print("\n=== Testing /simplify with correct API key (URL input) ===")
    response = requests.post(
        f"{BASE_URL}/simplify",
        json={"input": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/"},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_API_KEY}"
        }
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Source URL: {data.get('source_url', 'N/A')}")
        print(f"Recipe preview: {data.get('simplified_recipe', '')[:200]}...")
        print("✓ Successfully processed URL input")
    else:
        print(f"Response: {response.json()}")

def test_simplify_with_auth_search():
    """Test /simplify with correct API key and search query input"""
    print("\n=== Testing /simplify with correct API key (search query) ===")
    response = requests.post(
        f"{BASE_URL}/simplify",
        json={"input": "chocolate chip cookies"},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_API_KEY}"
        }
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Source URL: {data.get('source_url', 'N/A')}")
        print(f"Recipe preview: {data.get('simplified_recipe', '')[:200]}...")
        print("✓ Successfully processed search query")
    else:
        print(f"Response: {response.json()}")

def test_simplify_x_api_key_header():
    """Test /simplify with X-API-Key header instead of Authorization"""
    print("\n=== Testing /simplify with X-API-Key header ===")
    response = requests.post(
        f"{BASE_URL}/simplify",
        json={"input": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/"},
        headers={
            "Content-Type": "application/json",
            "X-API-Key": TEST_API_KEY
        }
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✓ X-API-Key header works")
    else:
        print(f"Response: {response.json()}")

if __name__ == "__main__":
    print("=" * 60)
    print("Recipeasy API Test Suite")
    print("=" * 60)
    print(f"\nNOTE: Make sure to:")
    print(f"1. Start the API server first: python recipeasy_api.py")
    print(f"2. Set API_KEY in recipeasy_api.py to: {TEST_API_KEY}")
    print(f"   OR set environment variable: export RECIPEASY_API_KEY='{TEST_API_KEY}'")
    
    try:
        # Test 1: Health endpoint (no auth)
        test_health_endpoint()
        
        # Test 2: No authentication
        test_simplify_no_auth()
        
        # Test 3: Wrong authentication
        test_simplify_wrong_auth()
        
        # Test 4: Correct auth with URL (requires OpenAI key)
        # test_simplify_with_auth_url()
        
        # Test 5: Correct auth with search query (requires OpenAI key)
        # test_simplify_with_auth_search()
        
        # Test 6: X-API-Key header
        # test_simplify_x_api_key_header()
        
        print("\n" + "=" * 60)
        print("Basic authentication tests completed successfully!")
        print("=" * 60)
        print("\nUncomment the other tests to verify full functionality")
        print("(requires OpenAI API key)")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Could not connect to {BASE_URL}")
        print("Make sure the API server is running: python recipeasy_api.py")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
