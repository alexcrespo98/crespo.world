#!/usr/bin/env python3
"""
Recipeasy API - AI-powered recipe simplifier
Runs on your homeserver and simplifies recipes from any website.

Usage:
    1. Install dependencies: pip install flask openai requests beautifulsoup4 flask-cors python-dotenv
    2. Set your OpenAI API key: export OPENAI_API_KEY="your-key-here"
       OR create a .env file with: OPENAI_API_KEY=your-key-here
    3. Run: python recipeasy_api.py
    4. Access at: http://localhost:5000 (or via your Tailscale IP)
"""

import os
import re
import requests
import subprocess
from urllib.parse import unquote
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


# Try to load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
# Enable CORS for all routes, allowing requests from crespo.world and any origin
CORS(app, origins=["*"])

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Recipe site patterns for search and validation
RECIPE_SITE_PATTERNS = [
    'allrecipes.com',
    'foodnetwork.com',
    'bonappetit.com',
    'epicurious.com',
    'seriouseats.com',
    'simplyrecipes.com',
    'tasteofhome.com'
]

RECIPE_KEYWORDS = ['recipe', 'food', 'cook', 'kitchen', 'tasty', 'delish']

def get_tailscale_ip():
    """Get the Tailscale IPv4 address of this machine"""
    try:
        result = subprocess.run(['tailscale', 'ip', '-4'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            ip = result.stdout.strip()
            if ip:
                return ip
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return None


def is_url(text):
    """Check if the input text is a URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(text) is not None

def is_recipe_url(url):
    """Check if URL is from a known recipe site or contains recipe keywords"""
    url_lower = url.lower()
    return (any(site in url_lower for site in RECIPE_SITE_PATTERNS) or
            any(keyword in url_lower for keyword in RECIPE_KEYWORDS))

def search_recipe(query, exclude_ingredients=''):
    """Search for a recipe using multiple strategies and return the first valid URL"""
    
    # Enhance query with exclusions if provided
    search_query = query
    if exclude_ingredients:
        # Add "without" to search query for better results
        excluded_items = [item.strip() for item in exclude_ingredients.split(',')]
        exclude_terms = ' '.join([f'without {item}' for item in excluded_items[:2]])  # Limit to first 2 for search
        search_query = f"{query} {exclude_terms}"
        print(f"Enhanced search query: {search_query}")
    
    # Strategy 1: Try popular recipe sites directly
    recipe_sites = [
        f"https://www.allrecipes.com/search?q={search_query.replace(' ', '+')}",
        f"https://www.foodnetwork.com/search/{search_query.replace(' ', '-')}-",
        f"https://www.bonappetit.com/search?q={search_query.replace(' ', '+')}",
        f"https://www.epicurious.com/search/{search_query.replace(' ', '%20')}",
        f"https://www.seriouseats.com/search?q={search_query.replace(' ', '+')}",
    ]
    
    print(f"Trying direct recipe site searches for: {search_query}")
    for site_url in recipe_sites[:2]:  # Try first 2 sites
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(site_url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for recipe links in search results
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if href.startswith('http') and is_recipe_url(href):
                        print(f"Found recipe URL: {href}")
                        return href
        except Exception as e:
            print(f"Error trying recipe site {site_url}: {e}")
            continue
    
    # Strategy 2: Try Google search with improved parsing
    try:
        print(f"Trying Google search for: {search_query}")
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}+recipe"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple methods to extract URLs
        # Method 1: Look for /url?q= pattern
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '/url?q=' in href:
                try:
                    url = href.split('/url?q=')[1].split('&')[0]
                    url = unquote(url)
                    if url.startswith('http') and 'google.com' not in url.lower() and is_recipe_url(url):
                        print(f"Found recipe URL from Google: {url}")
                        return url
                except Exception:
                    continue
        
        # Method 2: Look for direct recipe site links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href.startswith('http') and any(site in href.lower() for site in RECIPE_SITE_PATTERNS):
                print(f"Found direct recipe URL: {href}")
                return href
                
    except Exception as e:
        print(f"Error with Google search: {e}")
    
    # Strategy 3: Try DuckDuckGo as a fallback
    try:
        print(f"Trying DuckDuckGo search for: {search_query}")
        search_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}+recipe"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for link in soup.find_all('a', href=True, class_='result__a'):
            href = link.get('href', '')
            if href.startswith('http') and is_recipe_url(href):
                print(f"Found recipe URL from DuckDuckGo: {href}")
                return href
    except Exception as e:
        print(f"Error with DuckDuckGo search: {e}")
    
    print(f"Could not find recipe URL for query: {query}")
    return None

def fetch_webpage_content(url):
    """Fetch and extract text content from a webpage"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Limit to first 8000 characters to avoid token limits
        return text[:8000]
    except Exception as e:
        print(f"Error fetching webpage: {e}")
        raise

def simplify_recipe_with_ai(content, include_optional=True, unit_preference='original', exclude_ingredients=''):
    """Use OpenAI to extract and simplify the recipe"""
    try:
        # Build unit conversion instructions
        unit_instructions = ""
        if unit_preference == 'metric':
            unit_instructions = """
UNIT CONVERSION:
- Convert ALL measurements to metric (grams, ml, celsius)
- For dry ingredients: provide grams AND practical volume (e.g., "100g flour (about 3/4 cup)")
- For liquids: provide ml AND practical volume (e.g., "240ml milk (1 cup)")
- For items like meat: use grams AND practical descriptions (e.g., "450g chicken breast (2 medium breasts)")
"""
        elif unit_preference == 'imperial':
            unit_instructions = """
UNIT CONVERSION:
- Convert ALL measurements to imperial (cups, tablespoons, teaspoons, fahrenheit)
- For weights: convert to volume when practical (e.g., "1 cup flour" instead of "125g")
- For items like meat: use practical descriptions (e.g., "2 medium chicken breasts" instead of "1 pound")
- Provide ounces AND volume for clarity (e.g., "8oz (1 cup)")
"""
        
        optional_instructions = ""
        if not include_optional:
            optional_instructions = "- EXCLUDE all optional ingredients and garnishes"
        
        exclude_instructions = ""
        if exclude_ingredients:
            exclude_instructions = f"""
INGREDIENT EXCLUSIONS:
The user does NOT have these ingredients: {exclude_ingredients}
- If searching for a recipe, find one that AVOIDS these ingredients when possible
- If given a specific recipe URL that uses these ingredients, provide SUBSTITUTIONS
- Mark substitutions clearly with [SUBSTITUTION] tag like: "- 1 cup milk [SUBSTITUTION: use almond milk or water]"
- If no good substitution exists, note "[EXCLUDED - optional]" for optional ingredients
- Prioritize recipes that naturally don't use the excluded ingredients
"""
        
        system_prompt = f"""You are a recipe extraction expert. Your job is to extract recipes from web content and format them in a clean, no-nonsense way.

CRITICAL REQUIREMENTS:
1. Extract ALL ingredients with SPECIFIC measurements (NEVER use ranges like "2-3 cups")
2. For ranges, always use the middle or most practical value (e.g., "2.5 cups" or round to "2.5 cups")
3. Extract ALL instructions in order
4. Format EXACTLY as shown below
5. Remove ALL fluff, stories, tips, and extra content
6. ALWAYS include preheat temperature if there's baking
7. ALWAYS include prep steps like "line baking sheet" at the start of instructions
{optional_instructions}
{exclude_instructions}

MEASUREMENT RULES:
- NO RANGES: Convert "2-3 teaspoons" to "2.5 teaspoons" or "2.5 tsp"
- NO RANGES: Convert "1/2 to 1 cup" to "3/4 cup"
- Be specific and practical
- Round to common fractions (1/4, 1/3, 1/2, 2/3, 3/4) when possible
{unit_instructions}

OUTPUT FORMAT (MUST MATCH EXACTLY):
INGREDIENTS:
- ingredient 1 with measurement
- ingredient 2 with measurement
(etc.)

INSTRUCTIONS:
1. Preheat oven to [temperature] (if applicable)
2. Line/prepare pans (if applicable)
3. [clear, direct instruction]
4. [clear, direct instruction]
(etc.)

CRITICAL FORMATTING RULES:
- Instructions MUST be numbered with format "1. ", "2. ", "3. " etc. (number, period, space)
- NEVER use "Step 1:" or "1)" or any other format
- ALWAYS use the exact format shown above

Be concise but complete. Each instruction should be one clear action."""

        user_prompt = f"""Extract and simplify this recipe. Remove all stories, tips, and fluff. 
Format it with INGREDIENTS first (with measurements), then INSTRUCTIONS (numbered steps).

Content:
{content}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using cost-effective model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent formatting
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        raise

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'version': '1.0',
        'message': 'Recipeasy API is running'
    })

@app.route('/simplify', methods=['POST'])
def simplify():
    """Main endpoint to simplify recipes"""
    try:
        data = request.json
        if not data or 'input' not in data:
            return jsonify({'error': 'Missing "input" field in request'}), 400
        
        user_input = data['input'].strip()
        if not user_input:
            return jsonify({'error': 'Input cannot be empty'}), 400
        
        # Get optional parameters
        include_optional = data.get('include_optional', True)
        unit_preference = data.get('unit_preference', 'original')  # 'metric', 'imperial', or 'original'
        exclude_ingredients = data.get('exclude_ingredients', '')  # comma-separated ingredients to exclude
        
        # Determine if input is URL or search query
        if is_url(user_input):
            recipe_url = user_input
            print(f"Processing URL: {recipe_url}")
        else:
            print(f"Searching for recipe: {user_input}")
            recipe_url = search_recipe(user_input, exclude_ingredients)
            if not recipe_url:
                error_msg = (
                    f'Could not find a recipe for "{user_input}". '
                    'Try: (1) A direct recipe URL, (2) A more specific search like "butter chicken recipe", '
                    'or (3) A recipe from AllRecipes, Food Network, or similar sites.'
                )
                print(f"ERROR: {error_msg}")
                return jsonify({'error': error_msg}), 404
            print(f"Found recipe URL: {recipe_url}")
        
        # Fetch webpage content
        print("Fetching webpage content...")
        content = fetch_webpage_content(recipe_url)
        
        # Simplify with AI
        print("Simplifying recipe with AI...")
        simplified = simplify_recipe_with_ai(content, include_optional, unit_preference, exclude_ingredients)
        
        return jsonify({
            'simplified_recipe': simplified,
            'source_url': recipe_url
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch recipe: {str(e)}'}), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API information"""
    return jsonify({
        'name': 'Recipeasy API',
        'version': '1.0',
        'endpoints': {
            '/health': 'GET - Health check',
            '/simplify': 'POST - Simplify a recipe (requires "input" field with URL or recipe name)',
        },
        'example': {
            'method': 'POST',
            'endpoint': '/simplify',
            'body': {
                'input': 'https://example.com/recipe or "chocolate chip cookies"'
            }
        }
    })

if __name__ == '__main__':
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("=" * 60)
        print("WARNING: OPENAI_API_KEY environment variable not set!")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        print("Or create a .env file with: OPENAI_API_KEY=your-key-here")
        print("=" * 60)
    
    # Get Tailscale IP
    tailscale_ip = get_tailscale_ip()
    
    print("\n" + "=" * 60)
    print("Recipeasy API Server Starting")
    print("=" * 60)
    print(f"Server will be available at:")
    print(f"  - http://localhost:5000")
    print(f"  - http://0.0.0.0:5000")
    if tailscale_ip:
        print(f"  - http://{tailscale_ip}:5000")
        print(f"\nTailscale IP detected: {tailscale_ip}")
        print(f"API endpoint: http://{tailscale_ip}:5000/simplify")
    else:
        print(f"  - http://[your-tailscale-ip]:5000")
        print(f"\nNote: Tailscale IP could not be auto-detected")
    print("\nEndpoints:")
    print("  GET  /health   - Health check")
    print("  POST /simplify - Simplify recipe")
    print("=" * 60 + "\n")
    
    # Run the server
    # Using 0.0.0.0 to allow external connections (Tailscale)
    app.run(host='0.0.0.0', port=5000, debug=True)
