#!/bin/bash
echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║     SKYNET V2.0 — UGC EMPIRE         ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

ROUTER_URL="${ROUTER_URL:-https://wondering-omissions-midwest-lexington.trycloudflare.com}"
ROUTER_KEY="${ROUTER_KEY:-sk-8028a980b0c7366a-4a45za-36eef5ef}"
export ROUTER_URL ROUTER_KEY

check_deps() {
    python3 -c "import mcp, requests" 2>/dev/null && return 0
    echo "[+] Installing dependencies..."
    pip install -r requirements.txt -q
}

check_deps

case "${1:-help}" in
    campaign)
        shift
        python3 -m ugc_ai_overpower.main campaign "$@"
        ;;
    server|mcp)
        echo "[+] Starting MCP server..."
        python3 -m ugc_ai_overpower.main server
        ;;
    analyze)
        shift
        python3 -m ugc_ai_overpower.main analyze "$@"
        ;;
    search)
        shift
        python3 -m ugc_ai_overpower.main search "$@"
        ;;
    influencers|list)
        python3 -m ugc_ai_overpower.main list-influencers
        ;;
    generate-personas)
        python3 -m ugc_ai_overpower.main generate-personas
        ;;
    help|--help|-h)
        echo "Commands:"
        echo "  campaign <product>   Start a full UGC campaign"
        echo "  server               Start MCP server (for A2A)"
        echo "  analyze <product>    Analyze product with AI"
        echo "  search <keyword>     Search affiliate products"
        echo "  influencers          List all AI influencer personas"
        echo "  generate-personas    Generate detailed personas"
        echo ""
        echo "Env:"
        echo "  ROUTER_URL   9router base URL (default: http://localhost:20128)"
        echo "  ROUTER_KEY   9router API key"
        ;;
    *)
        python3 -m ugc_ai_overpower.main "$@"
        ;;
esac