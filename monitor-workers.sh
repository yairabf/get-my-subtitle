#!/bin/bash
# Monitor all workers and system status

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Function to print section header
print_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
}

# Function to check if service is running
check_service() {
    local name=$1
    local port=$2
    
    if nc -z localhost "$port" 2>/dev/null; then
        echo -e "${GREEN}✅ $name${NC} (port $port)"
        return 0
    else
        echo -e "${RED}❌ $name${NC} (port $port) - Not accessible"
        return 1
    fi
}

# Function to get queue status
get_queue_status() {
    local response=$(curl -s http://localhost:8000/queue/status 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        echo -e "${RED}Failed to get queue status${NC}"
    fi
}

# Function to get health status
get_health() {
    local response=$(curl -s http://localhost:8000/health 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        echo -e "${RED}Manager API not responding${NC}"
    fi
}

# Function to list recent jobs
get_recent_jobs() {
    local response=$(curl -s http://localhost:8000/subtitles 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        echo "$response" | python3 -m json.tool 2>/dev/null | head -50 || echo "$response"
    else
        echo -e "${RED}Failed to get jobs${NC}"
    fi
}

# Function to check Docker services
check_docker_services() {
    print_header "🐳 Docker Services Status"
    docker-compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "NAME|rabbitmq|redis" || echo "No Docker services found"
}

# Function to check infrastructure
check_infrastructure() {
    print_header "🔌 Infrastructure Status"
    check_service "Redis" 6379
    check_service "RabbitMQ" 5672
    check_service "Manager API" 8000
    check_service "Scanner Webhook" 8001
}

# Function to show worker processes
show_worker_processes() {
    print_header "👷 Worker Processes"
    echo -e "${BLUE}Python processes:${NC}"
    ps aux | grep -E "[p]ython.*(main\.py|worker\.py)" | awk '{printf "  PID: %-6s %s\n", $2, substr($0, index($0,$11))}'
}

# Function to show logs (last 10 lines from each service)
show_recent_logs() {
    print_header "📋 Recent Logs"
    
    if [ -d "logs" ]; then
        for logfile in logs/*.log; do
            if [ -f "$logfile" ]; then
                service=$(basename "$logfile" .log)
                echo -e "\n${YELLOW}━━━ $service ━━━${NC}"
                tail -5 "$logfile" 2>/dev/null | sed 's/^/  /'
            fi
        done
    else
        echo "No log files found in logs/ directory"
    fi
}

# Main monitoring loop
if [ "$1" == "--once" ]; then
    # Run once and exit
    check_docker_services
    check_infrastructure
    show_worker_processes
    
    print_header "🏥 Manager API Health"
    get_health
    
    print_header "📊 Queue Status"
    get_queue_status
    
    print_header "📝 Recent Jobs (last 5)"
    get_recent_jobs | head -30
    
    show_recent_logs
else
    # Continuous monitoring
    while true; do
        clear
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║        Subtitle Management System - Worker Monitor          ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
        echo -e "${YELLOW}Press Ctrl+C to exit${NC}\n"
        
        check_docker_services
        check_infrastructure
        show_worker_processes
        
        print_header "🏥 Manager API Health"
        get_health
        
        print_header "📊 Queue Status"
        get_queue_status
        
        print_header "📝 Recent Jobs (last 3)"
        get_recent_jobs | head -20
        
        echo -e "\n${YELLOW}Refreshing in 5 seconds... (Ctrl+C to exit)${NC}"
        sleep 5
    done
fi



