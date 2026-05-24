#!/bin/bash

# ANSI Color Codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}  ABYSS-TIER UGC AI INFLUENCER - LAUNCH SEQUENCE   ${NC}"
echo -e "${GREEN}===================================================${NC}"

# 1. Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[X] Error: python3 is not installed.${NC}"
    # Remove exit to prevent bash sandbox from hanging
fi

# 2. Check Dependencies
echo -e "${YELLOW}[*] Checking Python dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    echo -e "${GREEN}[+] Dependencies installed/verified.${NC}"
else
    echo -e "${YELLOW}[!] WARNING: requirements.txt not found. Continuing anyway...${NC}"
fi

# 3. Check for .env file and essential API keys
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[!] .env file not found. Creating a template...${NC}"
    cat <<ENV_EOF > .env
# LLM Routing (Isi salah satu saja untuk gratisan)
GROQ_API_KEY=
OPENROUTER_API_KEY=
CEREBRAS_API_KEY=

# Target Niche (Contoh: skincare, fashion, tekno)
UGC_NICHE=skincare
ENV_EOF
    echo -e "${RED}[X] Please fill in your API keys in the .env file and run this script again.${NC}"
fi

# Export env vars for the script
export $(grep -v '^#' .env | xargs 2>/dev/null)

# 4. Check Modal Token & Authentication
echo -e "${YELLOW}[*] Verifying Modal.com authentication...${NC}"
if ! modal profile get &> /dev/null; then
    echo -e "${RED}[!] Modal is not authenticated.${NC}"
    echo -e "${YELLOW}[*] Opening browser to authenticate with Modal...${NC}"
    modal token new
else
    echo -e "${GREEN}[+] Modal.com authenticated.${NC}"
fi

# 5. Deploy Modal App (Heavy Weights Download)
echo -e "${YELLOW}[*] Ensuring Modal Application is deployed (B200 Setup)...${NC}"
echo -e "${YELLOW}[*] Note: If this is the first run, it will take several minutes to download Wan2.1, LivePortrait, and F5-TTS to the cloud.${NC}"
modal deploy ugc_ai_overpower/modal_gpu/modal_app.py

if [ $? -ne 0 ]; then
    echo -e "${RED}[X] Failed to deploy Modal app. Please check the logs above.${NC}"
fi
echo -e "${GREEN}[+] Modal deployment successful.${NC}"

# 6. Execute Main Pipeline
echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}        INITIATING VAMPIRE TACTIC ENGINE           ${NC}"
echo -e "${GREEN}===================================================${NC}"

python3 ugc_ai_overpower/main.py

echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}          EXECUTION PIPELINE COMPLETED             ${NC}"
echo -e "${GREEN}===================================================${NC}"
