#!/bin/bash
# Real-time monitoring of all workers and translation flow

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Function to print header
print_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
}

# Function to get queue status
get_queue_status() {
    local response=$(curl -s http://localhost:8000/queue/status 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Download Queue: {data.get('download_queue_size', 0)} messages\")
print(f\"Translation Queue: {data.get('translation_queue_size', 0)} messages\")
print(f\"Active Downloaders: {data.get('active_workers', {}).get('downloader', 0)}\")
print(f\"Active Translators: {data.get('active_workers', {}).get('translator', 0)}\")
" 2>/dev/null || echo "$response"
    else
        echo -e "${RED}Manager API not responding${NC}"
    fi
}

# Function to tail logs with filtering
tail_logs() {
    local service=$1
    local pattern=$2
    local count=${3:-5}
    
    local logfile=$(find logs -name "${service}_*.log" -type f -exec ls -t {} + 2>/dev/null | head -1)
    if [ -n "$logfile" ] && [ -f "$logfile" ]; then
        if [ -n "$pattern" ]; then
            tail -100 "$logfile" 2>/dev/null | grep -i "$pattern" | tail -$count | sed 's/^/  /'
        else
            tail -$count "$logfile" 2>/dev/null | sed 's/^/  /'
        fi
    else
        echo -e "  ${YELLOW}No log file found${NC}"
    fi
}

# Main monitoring loop
clear
while true; do
    clear
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     Subtitle Management System - Real-Time Monitor           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo -e "${YELLOW}Press Ctrl+C to exit${NC}\n"
    
    # Queue Status
    print_header "📊 Queue Status"
    get_queue_status
    
    # Worker Processes
    print_header "👷 Active Workers"
    echo -e "${BLUE}Python processes:${NC}"
    ps aux | grep -E "[p]ython.*(main\.py|worker\.py)" | awk '{printf "  %-8s %s\n", $2, substr($0, index($0,$11))}' || echo "  No workers found"
    
    # Recent Translation Events
    print_header "🔄 Translation Flow (Last 3 events)"
    echo -e "${MAGENTA}Downloader → Manager → Translator${NC}\n"
    
    echo -e "${YELLOW}1. Downloader (Published Translation Events):${NC}"
    tail_logs "downloader" "Published SUBTITLE_TRANSLATE_REQUESTED" 3
    
    echo -e "\n${YELLOW}2. Manager (Processing Translation Events):${NC}"
    tail_logs "manager" "Processing translation request\|Received event.*TRANSLATE\|enqueue.*translation" 3
    
    echo -e "\n${YELLOW}3. Translator (Received Translation Tasks):${NC}"
    tail_logs "translator" "RECEIVED TRANSLATION TASK\|Translation started\|Translation completed" 3
    
    # Recent Activity
    print_header "📋 Recent Activity (Last 2 lines per service)"
    echo -e "${YELLOW}Scanner:${NC}"
    tail_logs "scanner" "" 2
    
    echo -e "\n${YELLOW}Downloader:${NC}"
    tail_logs "downloader" "" 2
    
    echo -e "\n${YELLOW}Manager:${NC}"
    tail_logs "manager" "" 2
    
    echo -e "\n${YELLOW}Translator:${NC}"
    tail_logs "translator" "" 2
    
    echo -e "\n${YELLOW}Consumer:${NC}"
    tail_logs "consumer" "" 2
    
    # Footer
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Refreshing in 3 seconds... (Ctrl+C to exit)${NC}"
    sleep 3
done






