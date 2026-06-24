#!/usr/bin/env python3
"""
Recipeasy API v3.0 - AI-powered recipe simplifier using Ollama
Accepts: URL, raw HTML, raw text, or search query
American units by default. /chat endpoint for recipe Q&A.
"""

import os
import re
import sqlite3
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["*"])

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
RATE_LIMIT_PER_DAY = 50
DB_PATH = "/Users/crespo/recipeasy/usage.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --- DATABASE ---

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        input TEXT,
        source_url TEXT,
        success INTEGER DEFAULT 1
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ip_ts ON usage(ip, timestamp)")
    conn.commit()
    conn.close()

def check_rate_limit(ip):
    db = get_db()
    cutoff = (datetime.now() - timedelta(days=1)).isoformat()
    row = db.execute("SELECT COUNT(*) as c FROM usage WHERE ip=? AND timestamp>?", (ip, cutoff)).fetchone()
    return row["c"] < RATE_LIMIT_PER_DAY

def log_usage(ip, input_text, source_url=None, success=True):
    db = get_db()
    db.execute("INSERT INTO usage (ip, timestamp, input, source_url, success) VALUES (?,?,?,?,?)",
               (ip, datetime.now().isoformat(), input_text, source_url, 1 if success else 0))
    db.commit()

# --- INPUT HANDLING ---

def is_url(text):
    return bool(re.match(r"^https?://", text.strip(), re.IGNORECASE))

def looks_like_html(text):
    return bool(re.search(r"<(html|body|div|p|ul|ol|li|h[1-6]|span|article|section)", text, re.IGNORECASE))

def extract_text_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
        el.decompose()
    text = soup.get_text(separator=" ")
    lines = (l.strip() for l in text.splitlines())
    chunks = (p.strip() for line in lines for p in line.split("  "))
    return " ".join(c for c in chunks if c)[:8000]

def fetch_url_content(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return extract_text_from_html(resp.text)

def search_for_recipe(query):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(f"https://www.allrecipes.com/search?q={query.replace(' ', '+')}", headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/recipe/" in href and href.startswith("http"):
                    return href
    except Exception as e:
        print(f"AllRecipes failed: {e}")
    try:
        resp = requests.get(f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}+recipe+site:allrecipes.com", headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", class_="result__a", href=True):
            if a["href"].startswith("http"):
                return a["href"]
    except Exception as e:
        print(f"DuckDuckGo failed: {e}")
    return None

# --- OLLAMA ---

SYSTEM_SIMPLIFY = """You are a recipe extraction expert.

RULES:
- American units only: cups, tablespoons, teaspoons, oz, lbs, degrees F
- Convert any metric to American (240ml = 1 cup, 100g flour = 3/4 cup)
- No measurement ranges — use the middle value (2-3 cups = 2.5 cups)
- Remove all stories, tips, ads, and fluff
- Include preheat step if baking

OUTPUT FORMAT — follow exactly, no deviations:
TITLE: [recipe name]

INGREDIENTS:
- [amount] [unit] [ingredient]

INSTRUCTIONS:
1. [step]
2. [step]

Numbered steps only. One action per step. Be concise."""

def call_ollama(messages, timeout=90):
    resp = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": OLLAMA_MODEL, "messages": messages, "stream": False, "options": {"temperature": 0.3, "num_predict": 2000}},
        timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()

def simplify_with_ollama(content):
    return call_ollama([
        {"role": "system", "content": SYSTEM_SIMPLIFY},
        {"role": "user", "content": f"Extract and simplify this recipe:\n\n{content}"}
    ])

def chat_with_ollama(recipe_text, user_message, history):
    system = f"""You are a helpful cooking assistant. The user is viewing this recipe:

{recipe_text}

Answer questions about this recipe. Be concise and practical. If asked something unrelated to cooking or this recipe, redirect politely."""
    messages = [{"role": "system", "content": system}]
    for turn in history:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})
    messages.append({"role": "user", "content": user_message})
    return call_ollama(messages, timeout=60)

# --- ENDPOINTS ---

def get_ip():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return ip.split(",")[0].strip()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": OLLAMA_MODEL, "rate_limit": f"{RATE_LIMIT_PER_DAY}/day"})

@app.route("/stats", methods=["GET"])
def stats():
    db = get_db()
    today = datetime.now().date().isoformat()
    today_count = db.execute("SELECT COUNT(*) as c FROM usage WHERE timestamp LIKE ?", (f"{today}%",)).fetchone()["c"]
    total = db.execute("SELECT COUNT(*) as c FROM usage").fetchone()["c"]
    unique_today = db.execute("SELECT COUNT(DISTINCT ip) as c FROM usage WHERE timestamp LIKE ?", (f"{today}%",)).fetchone()["c"]
    return jsonify({"today": {"requests": today_count, "unique_users": unique_today}, "total": total})

@app.route("/simplify", methods=["POST"])
def simplify():
    try:
        ip = get_ip()
        if not check_rate_limit(ip):
            return jsonify({"error": f"Rate limit: {RATE_LIMIT_PER_DAY} requests per day."}), 429
        data = request.json
        if not data or not data.get("input", "").strip():
            return jsonify({"error": "Missing input"}), 400
        user_input = data["input"].strip()
        source_url = None

        if is_url(user_input):
            source_url = user_input
            content = fetch_url_content(source_url)
        elif looks_like_html(user_input):
            content = extract_text_from_html(user_input)
        elif len(user_input) > 200:
            content = user_input[:8000]
        else:
            source_url = search_for_recipe(user_input)
            if not source_url:
                log_usage(ip, user_input[:200], success=False)
                return jsonify({"error": f"Could not find a recipe for \"{user_input}\". Try pasting a URL or the recipe text."}), 404
            content = fetch_url_content(source_url)

        simplified = simplify_with_ollama(content)
        log_usage(ip, user_input[:200], source_url, success=True)
        return jsonify({"simplified_recipe": simplified, "source_url": source_url})

    except Exception as e:
        print(f"Error in /simplify: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        if not data or not data.get("message", "").strip():
            return jsonify({"error": "Missing message"}), 400
        recipe = data.get("recipe", "")
        message = data["message"].strip()
        history = data.get("history", [])
        reply = chat_with_ollama(recipe, message, history)
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"Error in /chat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def index():
    return jsonify({"name": "Recipeasy API", "version": "3.0", "model": OLLAMA_MODEL})

if __name__ == "__main__":
    init_db()
    print(f"Recipeasy API v3.0 — {OLLAMA_MODEL} — port 8092")
    app.run(host="0.0.0.0", port=8092, debug=False)