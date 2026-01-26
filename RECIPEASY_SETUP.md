# Recipeasy Integration Guide

## What You Have Now

✅ **Frontend** (`recipeasy.html`) - Deployed on crespo.world
✅ **Backend API** (`recipeasy_api.py`) - Ready to run on your homeserver
✅ **Dependencies** (`recipeasy_requirements.txt`) - All packages needed

## What You Need to Do

### 1. Get an OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign up/login
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)
5. **Cost**: ~$0.01-0.05 per recipe with GPT-4o-mini

**Alternative**: Use Claude API from Anthropic (https://console.anthropic.com/)
- Would require modifying the code to use Claude instead of OpenAI

### 2. Set Up Your Homeserver

SSH into your homeserver and run these commands:

```bash
# Navigate to where you want to run the API
cd ~
mkdir recipeasy-api
cd recipeasy-api

# Copy the API files to your homeserver
# (You'll need to transfer recipeasy_api.py and recipeasy_requirements.txt)
# Use scp, git clone, or any file transfer method you prefer

# Install Python dependencies
pip install -r recipeasy_requirements.txt

# Set your OpenAI API key (choose one method):

# Method A: Environment variable (temporary - only for current session)
export OPENAI_API_KEY="sk-your-key-here"

# Method B: .env file (recommended - persists)
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Method C: Add to your shell profile (permanent)
echo 'export OPENAI_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Run the API Server

```bash
# Start the server
python recipeasy_api.py

# You should see:
# 🍳 Recipeasy API Server Starting
# Server will be available at:
#   - http://localhost:5000
#   - http://0.0.0.0:5000
#   - http://[your-tailscale-ip]:5000
```

### 4. Find Your Tailscale IP

```bash
# On your homeserver, run:
tailscale ip -4

# Example output: 100.64.1.2
# This is your Tailscale IP that you'll use in the frontend
```

### 5. Configure the Frontend

1. Go to https://crespo.world/recipeasy.html (once deployed)
2. In the "API Configuration" section:
   - Enter your API endpoint URL:
     - Format: `http://[your-tailscale-ip]:5000/simplify`
     - Example: `http://100.64.1.2:5000/simplify`
     - Or use Tailscale hostname: `http://homeserver.tailnet.ts.net:5000/simplify`
3. Click "Save Configuration"
4. Click "Test Connection" to verify it works

### 6. Test It Out

1. Enter this URL in the recipe input:
   ```
   https://joyfoodsunshine.com/the-most-amazing-chocolate-chip-cookies/
   ```
2. Click "Simplify Recipe"
3. Wait 5-10 seconds for the AI to process
4. You should see ingredients first, then numbered instructions!

## Running the API Permanently

To keep the API running even when you disconnect from SSH:

### Option A: Using screen (simple)
```bash
# Start a screen session
screen -S recipeasy

# Run the API
python recipeasy_api.py

# Detach from screen: Ctrl+A, then D
# Reattach later: screen -r recipeasy
```

### Option B: Using systemd (recommended for production)
```bash
# Create a systemd service file
sudo nano /etc/systemd/system/recipeasy.service

# Add this content (adjust paths to match your setup):
[Unit]
Description=Recipeasy API Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/recipeasy-api
Environment="OPENAI_API_KEY=sk-your-key-here"
ExecStart=/usr/bin/python3 /home/your-username/recipeasy-api/recipeasy_api.py
Restart=always

[Install]
WantedBy=multi-user.target

# Save and exit (Ctrl+X, Y, Enter)

# Enable and start the service
sudo systemctl enable recipeasy
sudo systemctl start recipeasy

# Check status
sudo systemctl status recipeasy
```

### Option C: Using nohup (quick and dirty)
```bash
nohup python recipeasy_api.py > recipeasy.log 2>&1 &
```

## Troubleshooting

### "Connection failed" in frontend
- Check if API is running: `curl http://localhost:5000/health`
- Verify Tailscale IP is correct: `tailscale ip -4`
- Check firewall allows port 5000
- Make sure you're on the same Tailscale network on both devices

### "OpenAI API key not set"
- Run: `echo $OPENAI_API_KEY` to verify it's set
- If using .env file, make sure it's in the same directory as the API script

### "Recipe not found" or timeout errors
- Some websites block scrapers - try a different recipe URL
- Check your internet connection on the homeserver
- Try using a recipe name search instead of a direct URL

### Rate limits or costs
- OpenAI has rate limits and costs per API call
- Using GPT-4o-mini keeps costs very low (~$0.01-0.05 per recipe)
- Monitor usage at: https://platform.openai.com/usage

## Security Notes

✅ **Safe**: API only accessible via Tailscale (private network)
✅ **Safe**: No public internet exposure needed
✅ **Safe**: API key stored on your homeserver only
⚠️ **Note**: API has no authentication - only you and people on your Tailscale network can access it

## Architecture Overview

```
[Browser on any device]
        ↓
[Tailscale network]
        ↓
[Your Homeserver running recipeasy_api.py]
        ↓
[OpenAI API] ← scrapes and simplifies recipes
        ↓
[Simplified recipe returned to browser]
```

## Need Help?

Use this prompt with a fresh agent to continue integration:

---

**INTEGRATION PROMPT FOR FRESH AGENT:**

I need help setting up the Recipeasy API on my homeserver. The codebase is at crespo.world and has these files:
- `recipeasy.html` - Frontend already deployed
- `recipeasy_api.py` - Backend API to run on my homeserver
- `recipeasy_requirements.txt` - Python dependencies
- `RECIPEASY_SETUP.md` - This setup guide

My homeserver details:
- OS: [YOUR OS - e.g., Ubuntu 22.04]
- Tailscale: [INSTALLED/NOT INSTALLED]
- Python version: [YOUR VERSION]
- Tailscale IP: [YOUR IP if known]

I need help with:
1. [Installing dependencies]
2. [Setting up the OpenAI API key]
3. [Running the server]
4. [Configuring the frontend to use my Tailscale IP]
5. [Making it run permanently]
6. [Other specific issues]

Please guide me step-by-step through the integration process.

---

Copy the above prompt and fill in your details when you're ready to set this up!
