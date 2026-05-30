#!/bin/bash

# ANSI Color Codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================================================${NC}"
echo -e "${GREEN}  SKYNET V2.0 (THE ABYSS-TIER UGC AI) - FULL AUTONOMOUS LAUNCH SEQUENCE  ${NC}"
echo -e "${GREEN}=========================================================================${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[X] Error: python3 is not installed.${NC}"
fi

echo -e "${YELLOW}[*] Checking Python dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
    echo -e "${GREEN}[+] Dependencies installed/verified.${NC}"
fi

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[!] .env file not found. Creating Skynet configuration template...${NC}"
    cat <<ENV_EOF > .env
# MULTI-KEY ROUTING (Round-Robin to bypass limits via 9router)
# Format: key1,key2,key3
GROQ_API_KEYS=
OPENROUTER_API_KEYS=
CEREBRAS_API_KEYS=

# TARGET NICHE
UGC_NICHE=skincare

# DATABASE VECTOR RAG (Mempalace / MongoDB Atlas)
MONGO_URI=mongodb+srv://simulated:simulated@simulated.mongodb.net

# AGENT HARNESS (Choose your Manager: claw-code | jcode | free-claude-code)
ACTIVE_AGENT_MANAGER=jcode
ENV_EOF
    echo -e "${RED}[X] Please fill in your API keys in the .env file and run this script again.${NC}"
fi

export $(grep -v '^#' .env | xargs 2>/dev/null)

echo -e "${CYAN}[*] Skynet Agent Manager Selected: ${ACTIVE_AGENT_MANAGER^^}${NC}"

echo -e "${YELLOW}[*] Verifying Modal.com authentication (GPU Offloading)...${NC}"
if ! modal profile get &> /dev/null; then
    echo -e "${RED}[!] Modal is not authenticated. Opening browser...${NC}"
    modal token new
else
    echo -e "${GREEN}[+] Modal.com authenticated.${NC}"
fi

echo -e "${YELLOW}[*] Ensuring SANA/Wan2.1 Modal Application is deployed...${NC}"
modal deploy ugc_ai_overpower/modal_gpu/modal_app.py

if [ $? -ne 0 ]; then
    echo -e "${RED}[X] Failed to deploy Modal app. Please check the logs above.${NC}"
fi
echo -e "${GREEN}[+] Modal Serverless GPU Deployment successful.${NC}"

echo -e "${GREEN}=========================================================================${NC}"
echo -e "${GREEN}     INITIATING VAMPIRE TACTIC ENGINE & COGNITIVE MUTATION MATRIX        ${NC}"
echo -e "${GREEN}=========================================================================${NC}"

python3 ugc_ai_overpower/main.py

echo -e "${GREEN}=========================================================================${NC}"
echo -e "${GREEN}        EXECUTION PIPELINE COMPLETED - STANDBY FOR AGENT COMMANDS        ${NC}"
echo -e "${GREEN}=========================================================================${NC}"
