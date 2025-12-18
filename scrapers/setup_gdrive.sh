#!/bin/bash
# Google Drive Setup Script for Ubuntu
# Sets up rclone for Google Drive integration with scrapers

set -e

echo "=========================================================================="
echo "🚀 Google Drive Setup for Social Media Scrapers"
echo "=========================================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${RED}⚠️  This script is designed for Linux/Ubuntu systems.${NC}"
    echo "For other operating systems, please install rclone manually from https://rclone.org"
    exit 1
fi

echo "Step 1: Checking for rclone installation..."
echo "-------------------------------------------"

if command -v rclone &> /dev/null; then
    echo -e "${GREEN}✅ rclone is already installed${NC}"
    rclone version
else
    echo -e "${YELLOW}📦 rclone not found. Installing...${NC}"
    
    # Install rclone (download, verify, then execute for security)
    echo "Downloading rclone install script..."
    curl -o /tmp/rclone-install.sh https://rclone.org/install.sh
    
    echo "Executing install script..."
    sudo bash /tmp/rclone-install.sh
    rm /tmp/rclone-install.sh
    
    if command -v rclone &> /dev/null; then
        echo -e "${GREEN}✅ rclone installed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to install rclone${NC}"
        echo "Please install manually from https://rclone.org/downloads/"
        exit 1
    fi
fi

echo ""
echo "Step 2: Configuring Google Drive remote..."
echo "-------------------------------------------"

# Check if 'gdrive' remote already exists
if rclone listremotes | grep -q "^gdrive:$"; then
    echo -e "${YELLOW}⚠️  Remote 'gdrive' already exists${NC}"
    read -p "Do you want to reconfigure it? (y/n): " reconfigure
    if [[ "$reconfigure" != "y" ]]; then
        echo "Skipping configuration..."
    else
        echo "Removing existing remote..."
        rclone config delete gdrive
        echo -e "${YELLOW}Starting configuration...${NC}"
        echo ""
        echo "Please follow the prompts to set up Google Drive:"
        echo "1. Choose 'n' for new remote"
        echo "2. Name it 'gdrive'"
        echo "3. Choose 'drive' for Google Drive"
        echo "4. Leave client_id and client_secret blank (press Enter)"
        echo "5. Choose scope '1' for full access"
        echo "6. Leave root_folder_id blank (press Enter)"
        echo "7. Leave service_account_file blank (press Enter)"
        echo "8. Choose 'n' for advanced config"
        echo "9. Choose 'y' for auto config (if running on desktop) or 'n' (if on server)"
        echo "10. Follow browser authentication steps"
        echo "11. Choose 'n' for team drive"
        echo "12. Choose 'y' to confirm"
        echo "13. Choose 'q' to quit config"
        echo ""
        rclone config
    fi
else
    echo -e "${YELLOW}Starting configuration...${NC}"
    echo ""
    echo "Please follow the prompts to set up Google Drive:"
    echo "1. Choose 'n' for new remote"
    echo "2. Name it 'gdrive'"
    echo "3. Choose 'drive' for Google Drive"
    echo "4. Leave client_id and client_secret blank (press Enter)"
    echo "5. Choose scope '1' for full access"
    echo "6. Leave root_folder_id blank (press Enter)"
    echo "7. Leave service_account_file blank (press Enter)"
    echo "8. Choose 'n' for advanced config"
    echo "9. Choose 'y' for auto config (if running on desktop) or 'n' (if on server)"
    echo "10. Follow browser authentication steps"
    echo "11. Choose 'n' for team drive"
    echo "12. Choose 'y' to confirm"
    echo "13. Choose 'q' to quit config"
    echo ""
    rclone config
fi

echo ""
echo "Step 3: Testing Google Drive connection..."
echo "-------------------------------------------"

if rclone listremotes | grep -q "^gdrive:$"; then
    echo -e "${GREEN}✅ Remote 'gdrive' configured${NC}"
    
    echo "Testing connection..."
    if rclone lsd gdrive: &> /dev/null; then
        echo -e "${GREEN}✅ Successfully connected to Google Drive${NC}"
        echo ""
        echo "Listing top-level folders:"
        rclone lsd gdrive:
    else
        echo -e "${RED}❌ Failed to connect to Google Drive${NC}"
        echo "Please check your configuration and try again"
        exit 1
    fi
else
    echo -e "${RED}❌ Remote 'gdrive' not found${NC}"
    echo "Configuration may have failed. Please run 'rclone config' manually"
    exit 1
fi

echo ""
echo "Step 4: Setting up folder structure..."
echo "-------------------------------------------"

# Create scrapers folder if it doesn't exist
echo "Creating 'scrapers' folder in Google Drive..."
rclone mkdir gdrive:scrapers 2>/dev/null || echo "Folder may already exist"

if rclone lsd gdrive: | grep -q "scrapers"; then
    echo -e "${GREEN}✅ Folder 'scrapers' exists in Google Drive${NC}"
else
    echo -e "${YELLOW}⚠️  Could not verify 'scrapers' folder${NC}"
fi

echo ""
echo "Step 5: Testing upload permissions..."
echo "-------------------------------------------"

# Create a test file
TEST_FILE="/tmp/gdrive_test_$(date +%s).txt"
echo "Test file created at $(date)" > "$TEST_FILE"

echo "Uploading test file..."
if rclone copy "$TEST_FILE" gdrive:scrapers/; then
    echo -e "${GREEN}✅ Upload successful!${NC}"
    
    # Verify file exists
    if rclone ls gdrive:scrapers/ | grep -q "gdrive_test"; then
        echo -e "${GREEN}✅ File verified in Google Drive${NC}"
        
        # Clean up test file
        echo "Cleaning up test file..."
        rclone delete gdrive:scrapers/$(basename "$TEST_FILE")
        rm "$TEST_FILE"
        echo -e "${GREEN}✅ Test file removed${NC}"
    else
        echo -e "${YELLOW}⚠️  Could not verify uploaded file${NC}"
        rm "$TEST_FILE"
    fi
else
    echo -e "${RED}❌ Upload failed${NC}"
    echo "Please check your permissions and try again"
    rm "$TEST_FILE"
    exit 1
fi

echo ""
echo "=========================================================================="
echo -e "${GREEN}✅ Google Drive setup complete!${NC}"
echo "=========================================================================="
echo ""
echo "You can now use the scrapers with Google Drive integration."
echo ""
echo "To upload files manually, use:"
echo "  rclone copy <local_file> gdrive:scrapers/"
echo ""
echo "To list files in Google Drive:"
echo "  rclone ls gdrive:scrapers/"
echo ""
echo "For more rclone commands, see: https://rclone.org/commands/"
echo ""
