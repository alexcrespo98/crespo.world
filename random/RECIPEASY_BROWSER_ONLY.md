# Recipeasy - Browser-Only Version

## Overview
Recipeasy now runs entirely in your browser without needing a Python server. All recipe fetching and AI simplification happens client-side using JavaScript.

## How It Works

### No Server Required
- Everything runs in your browser when you open `recipeasy.html`
- No need to install Python, Flask, or run any server
- Just open the HTML file in your browser and it works!

### Password Protection
- Page is protected with password: `0990`
- OpenAI API key is embedded in the HTML source code
- Password provides basic security, but key is visible to anyone with HTML source access

### Features
1. **Recipe Search**: Enter a search query like "chocolate chip cookies" to find recipes
2. **Direct URL**: Paste any recipe URL from popular sites (AllRecipes, Food Network, etc.)
3. **AI Simplification**: OpenAI API simplifies recipes to clean, easy-to-follow format
4. **Recipe Options**:
   - Include/exclude optional ingredients
   - Unit conversion (metric, imperial, or original)
5. **Recipe Multiplier**: Scale recipes up or down (0.5x to 4x)
6. **Interactive Checkboxes**: Track cooking progress
7. **Copy/Download**: Save recipes as text files

## Technical Details

### CORS Proxy
Since browsers can't directly fetch from most recipe sites due to CORS restrictions, the app uses CORS proxy services:

1. `https://api.allorigins.win/` (primary)
2. `https://corsproxy.io/` (fallback)
3. `https://api.codetabs.com/v1/proxy` (fallback)

**Important**: CORS proxies may be blocked by ad blockers or content blockers. If recipe search doesn't work:
- Disable ad blockers/content blockers
- Use a direct recipe URL instead of search
- Try a different browser

### OpenAI Integration
- Uses OpenAI API directly from browser
- Model: `gpt-4o-mini` (cost-effective)
- API key embedded in HTML source
- Temperature: 0.3 for consistent formatting

### Recipe Parsing
- Extracts ingredients with measurements
- Parses numbered instructions
- Supports recipe multiplier with fraction formatting
- Ingredient/instruction checkbox state saved to localStorage

## Comparison: Server vs Browser-Only

### Previous (Server-Based)
- ✅ More secure (API key on server)
- ✅ No CORS issues
- ❌ Requires Python server running
- ❌ Must install dependencies
- ❌ Server must be accessible over network

### Current (Browser-Only)
- ✅ No server required
- ✅ Works offline (after page loads)
- ✅ Easier to use (just open HTML)
- ❌ API key visible in source
- ❌ CORS proxies may be blocked
- ⚠️ Direct URLs more reliable than search

## Security Considerations

### API Key Exposure
The OpenAI API key is visible in the HTML source code. This is acceptable ONLY if:
1. You're running this on a personal device/server
2. The page is password-protected (as it is)
3. The API key has usage limits/billing alerts set up in OpenAI
4. You trust all users who can access the HTML file

For public-facing deployments, use proper server-side authentication instead.

### Recommendations
- Set up billing alerts in OpenAI dashboard
- Set usage limits on the API key
- Monitor API usage regularly
- Rotate the API key if compromised
- Consider using a server-based approach for public deployments

## Usage

### Basic Usage
1. Open `recipeasy.html` in your browser
2. Enter password: `0990`
3. Enter a recipe URL or search query
4. Click "Simplify Recipe"
5. View, scale, and track your recipe

### Best Practices
- **For Search**: Use specific queries like "chocolate chip cookie recipe"
- **For URLs**: Direct recipe URLs are more reliable than search
- **If CORS Blocked**: Disable ad blockers or use direct URLs
- **Popular Sites**: AllRecipes, Food Network, Bon Appétit, Epicurious all work well

## Troubleshooting

### "CORS proxies may be blocked" Error
**Problem**: CORS proxies are blocked by ad blocker or content blocker  
**Solution**: 
- Disable ad blockers/content blockers
- Use a direct recipe URL instead of search
- Try a different browser

### Recipe Not Found
**Problem**: Search couldn't find a recipe  
**Solution**: 
- Try a more specific search query
- Include the word "recipe" in your search
- Use a direct recipe URL from a recipe site

### OpenAI API Error
**Problem**: Error calling OpenAI API  
**Solution**: 
- Check if API key is valid
- Check OpenAI account has credits
- Check browser console for detailed error

## Files

### Modified
- `recipeasy.html` - Converted to browser-only version

### No Longer Needed
- `recipeasy_api.py` - Python server (can be deleted)
- `recipeasy_requirements.txt` - Python dependencies (can be deleted)

## Technical Implementation

### Key Functions
- `fetchRecipeContent()` - Fetches recipe HTML via CORS proxy
- `searchRecipe()` - Searches Google for recipe URLs
- `simplifyWithAI()` - Calls OpenAI API to simplify recipes
- `parseRecipe()` - Parses simplified recipe text
- `displayRecipe()` - Renders recipe with interactive elements
- `updateRecipeMultiplier()` - Scales recipe measurements

### Data Flow
```
User Input → isUrl() check → 
  ├─ URL → fetchRecipeContent()
  └─ Query → searchRecipe() → fetchRecipeContent()
    → simplifyWithAI() → parseRecipe() → displayRecipe()
```

### Local Storage
Recipe checkbox state is saved to localStorage using the recipe URL as key:
```javascript
{
  checkedInstructions: [1, 2, 5],
  checkedIngredients: [0, 3, 7],
  timestamp: 1234567890
}
```

## Future Enhancements

Potential improvements:
1. Recipe bookmarking/favorites
2. Print-friendly view
3. Shopping list generation
4. Meal planning features
5. Recipe notes/modifications
6. Server-based proxy to avoid CORS limitations
7. Multiple OpenAI API key rotation
8. Recipe import from PDF/image

## License
Part of crespo.world - Personal project
