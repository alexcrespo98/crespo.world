#!/usr/bin/env python3
"""
Recipeasy API - AI-powered recipe simplifier using Ollama
Runs on Petri, accessible via Tailscale Funnel.

Features:
- Uses local Ollama (qwen2.5:7b) instead of OpenAI
- Rate limited: 50 requests per IP per day
- Usage tracking with SQLite
- Public stats endpoint
"""

import os
import re
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from urllib.parse import unquote
from functools import wraps
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["*"])

# Configuration
OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
RATE_LIMIT_PER_DAY = 50
DB_PATH = "/Users/crespo/recipeasy/usage.db"

# Ensure directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ============================================================================
# DATABASE SETUP
# ============================================================================

def get_db():
    """Get database connection for current request"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            input TEXT,
            source_url TEXT,
            success INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_ip_timestamp 
        ON usage(ip, timestamp)
    """)
    conn.commit()
    conn.close()

def check_rate_limit(ip):
    """Check if IP has exceeded daily rate limit"""
    db = get_db()
    cutoff = (datetime.now() - timedelta(days=1)).isoformat()
    cursor = db.execute(
        "SELECT COUNT(*) as count FROM usage WHERE ip = ? AND timestamp > ?",
        (ip, cutoff)
    )
    count = cursor.fetchone()['count']
    return count < RATE_LIMIT_PER_DAY

def log_usage(ip, input_text, source_url=None, success=True):
    """Log API usage"""
    db = get_db()
    db.execute(
        "INSERT INTO usage (ip, timestamp, input, source_url, success) VALUES (?, ?, ?, ?, ?)",
        (ip, datetime.now().isoformat(), input_text, source_url, 1 if success else 0)
    )
    db.commit()

# ============================================================================
# RECIPE FETCHING AND PARSING
# ============================================================================

RECIPE_SITE_PATTERNS = [
    'allrecipes.com', 'foodnetwork.com', 'bonappetit.com',
    'epicurious.com', 'seriouseats.com', 'simplyrecipes.com',
    'tasteofhome.com', 'kingarthurbaking.com', 'nytcooking.com'
]

def is_url(text):
    """Check if text is a URL"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(text) is not None

def is_recipe_url(url):
    """Check if URL is from a recipe site"""
    url_lower = url.lower()
    return any(site in url_lower for site in RECIPE_SITE_PATTERNS)

def search_recipe(query):
    """Search for a recipe and return URL"""
    # Try AllRecipes search
    try:
        search_url = f"https://www.allrecipes.com/search?q={query.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '/recipe/' in href and href.startswith('http'):
                    return href
    except Exception as e:
        print(f"AllRecipes search failed: {e}")
    
    # Try DuckDuckGo
    try:
        search_url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}+recipe"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True, class_='result__a'):
            href = link.get('href', '')
            if href.startswith('http') and is_recipe_url(href):
                return href
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")
    
    return None

def fetch_webpage_content(url):
    """Fetch and extract text from webpage"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()
        
        # Get text
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:8000]
    except Exception as e:
        print(f"Error fetching webpage: {e}")
        raise

# ============================================================================
# AI SIMPLIFICATION WITH OLLAMA
# ============================================================================

def simplify_with_ollama(content, include_optional=True, unit_preference='original'):
    """Use Ollama to simplify recipe"""
    
    # Build unit instructions
    unit_instructions = ""
    if unit_preference == 'metric':
        unit_instructions = """
UNIT CONVERSION:
- Convert ALL measurements to metric (grams, ml, celsius)
- For dry ingredients: provide grams AND practical volume (e.g., "100g flour (about 3/4 cup)")
- For liquids: provide ml AND practical volume (e.g., "240ml milk (1 cup)")
"""
    elif unit_preference == 'imperial':
        unit_instructions = """
UNIT CONVERSION:
- Convert ALL measurements to imperial (cups, tablespoons, teaspoons, fahrenheit)
- For weights: convert to volume when practical (e.g., "1 cup flour" instead of "125g")
"""
    
    optional_instructions = ""
    if not include_optional:
        optional_instructions = "- EXCLUDE all optional ingredients and garnishes"
    
    system_prompt = f"""You are a recipe extraction expert. Extract recipes from web content and format cleanly.

CRITICAL REQUIREMENTS:
1. Extract ALL ingredients with SPECIFIC measurements (NEVER use ranges like "2-3 cups")
2. For ranges, use middle value (e.g., "2-3 cups" → "2.5 cups")
3. Extract ALL instructions in order
4. Remove ALL fluff, stories, tips
5. ALWAYS include preheat temperature if baking
{optional_instructions}

MEASUREMENT RULES:
- NO RANGES: Convert "2-3 teaspoons" to "2.5 teaspoons"
- Be specific and practical
- Round to common fractions (1/4, 1/3, 1/2, 2/3, 3/4)
{unit_instructions}

OUTPUT FORMAT (MUST MATCH EXACTLY):
INGREDIENTS:
- ingredient 1 with measurement
- ingredient 2 with measurement

INSTRUCTIONS:
1. Preheat oven to [temperature] (if applicable)
2. Line/prepare pans (if applicable)
3. [clear, direct instruction]

FORMATTING RULES:
- Instructions MUST be numbered: "1. ", "2. ", "3. "
- NEVER use "Step 1:" or "1)"
- Be concise but complete"""

    user_prompt = f"""Extract and simplify this recipe. Remove all stories and fluff.
Format with INGREDIENTS first (with measurements), then INSTRUCTIONS (numbered).

Content:
{content}"""

    try:
        response = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2000
                }
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return data['message']['content'].strip()
    except Exception as e:
        print(f"Ollama error: {e}")
        raise

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'model': OLLAMA_MODEL,
        'rate_limit': f'{RATE_LIMIT_PER_DAY} per day'
    })

@app.route('/stats', methods=['GET'])
def stats():
    """Usage statistics"""
    db = get_db()
    
    # Today's usage
    today = datetime.now().date().isoformat()
    cursor = db.execute(
        "SELECT COUNT(*) as count FROM usage WHERE timestamp LIKE ?",
        (f"{today}%",)
    )
    today_count = cursor.fetchone()['count']
    
    # Total usage
    cursor = db.execute("SELECT COUNT(*) as count FROM usage")
    total_count = cursor.fetchone()['count']
    
    # Unique IPs today
    cursor = db.execute(
        "SELECT COUNT(DISTINCT ip) as count FROM usage WHERE timestamp LIKE ?",
        (f"{today}%",)
    )
    unique_ips_today = cursor.fetchone()['count']
    
    return jsonify({
        'today': {
            'requests': today_count,
            'unique_users': unique_ips_today
        },
        'total_requests': total_count,
        'rate_limit': f'{RATE_LIMIT_PER_DAY} per IP per day'
    })

@app.route('/simplify', methods=['POST'])
def simplify():
    """Simplify a recipe"""
    try:
        # Get client IP
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ',' in ip:
            ip = ip.split(',')[0].strip()
        
        # Check rate limit
        if not check_rate_limit(ip):
            log_usage(ip, None, success=False)
            return jsonify({
                'error': f'Rate limit exceeded. Maximum {RATE_LIMIT_PER_DAY} requests per day.'
            }), 429
        
        # Parse request
        data = request.json
        if not data or 'input' not in data:
            return jsonify({'error': 'Missing "input" field'}), 400
        
        user_input = data['input'].strip()
        if not user_input:
            return jsonify({'error': 'Input cannot be empty'}), 400
        
        include_optional = data.get('include_optional', True)
        unit_preference = data.get('unit_preference', 'original')
        
        # Determine if URL or search query
        if is_url(user_input):
            recipe_url = user_input
            print(f"Processing URL: {recipe_url}")
        else:
            print(f"Searching for: {user_input}")
            recipe_url = search_recipe(user_input)
            if not recipe_url:
                log_usage(ip, user_input, success=False)
                return jsonify({
                    'error': f'Could not find recipe for "{user_input}". Try a direct URL.'
                }), 404
            print(f"Found: {recipe_url}")
        
        # Fetch content
        print("Fetching content...")
        content = fetch_webpage_content(recipe_url)
        
        # Simplify
        print("Simplifying with Ollama...")
        simplified = simplify_with_ollama(content, include_optional, unit_preference)
        
        # Log success
        log_usage(ip, user_input, recipe_url, success=True)
        
        return jsonify({
            'simplified_recipe': simplified,
            'source_url': recipe_url
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """API info"""
    return jsonify({
        'name': 'Recipeasy API',
        'version': '2.0',
        'model': OLLAMA_MODEL,
        'endpoints': {
            '/health': 'GET - Health check',
            '/stats': 'GET - Usage statistics',
            '/simplify': 'POST - Simplify recipe (JSON: {"input": "url or query"})'
        }
    })

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("Recipeasy API v2.0")
    print("=" * 60)
    print(f"Model: {OLLAMA_MODEL}")
    print(f"Rate limit: {RATE_LIMIT_PER_DAY} per IP per day")
    print(f"Database: {DB_PATH}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=8092, debug=False)
