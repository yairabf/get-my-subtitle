#!/bin/bash

# Manual Testing Helper Script
# This script helps automate common testing tasks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

check_service() {
    local service=$1
    local health=$(docker-compose ps $service | grep -c "healthy" || echo "0")
    
    if [ "$health" -gt 0 ]; then
        print_success "$service is healthy"
        return 0
    else
        print_error "$service is not healthy"
        return 1
    fi
}

# Main script
main() {
    local command=${1:-help}
    
    case $command in
        check-health)
            print_header "Checking Service Health"
            
            # Check Manager API
            if curl -s http://localhost:8000/health > /dev/null 2>&1; then
                print_success "Manager API is responding"
            else
                print_error "Manager API is not responding"
            fi
            
            # Check Redis
            if docker exec get-my-subtitle-redis-1 redis-cli ping > /dev/null 2>&1; then
                print_success "Redis is responding"
            else
                print_error "Redis is not responding"
            fi
            
            # Check RabbitMQ
            if curl -s -u guest:guest http://localhost:15672/api/overview > /dev/null 2>&1; then
                print_success "RabbitMQ is responding"
            else
                print_error "RabbitMQ is not responding"
            fi
            
            # Check Docker services
            check_service "manager" || true
            check_service "downloader" || true
            check_service "translator" || true
            check_service "consumer" || true
            ;;
            
        submit-job)
            print_header "Submitting Test Job"
            
            local video_url=${2:-"https://example.com/test-video.mp4"}
            local video_title=${3:-"Test Video"}
            
            print_info "Video URL: $video_url"
            print_info "Video Title: $video_title"
            echo ""
            
            response=$(curl -s -X POST http://localhost:8000/subtitles/download \
                -H "Content-Type: application/json" \
                -d "{
                    \"video_url\": \"$video_url\",
                    \"video_title\": \"$video_title\",
                    \"language\": \"he\",
                    \"preferred_sources\": [\"opensubtitles\"]
                }")
            
            echo "$response" | jq .
            
            job_id=$(echo "$response" | jq -r '.job_id')
            
            if [ "$job_id" != "null" ]; then
                print_success "Job submitted: $job_id"
                echo ""
                print_info "Check status with: ./scripts/test_manual.sh check-job $job_id"
                print_info "Watch status with: ./scripts/test_manual.sh watch-job $job_id"
            else
                print_error "Failed to submit job"
            fi
            ;;
            
        check-job)
            local job_id=$2
            
            if [ -z "$job_id" ]; then
                print_error "Job ID required"
                echo "Usage: $0 check-job <job_id>"
                exit 1
            fi
            
            print_header "Checking Job Status: $job_id"
            
            # Get status
            echo "Status:"
            curl -s "http://localhost:8000/subtitles/$job_id/status" | jq .
            
            echo ""
            echo "Events:"
            curl -s "http://localhost:8000/subtitles/$job_id/events" | jq .
            ;;
            
        watch-job)
            local job_id=$2
            
            if [ -z "$job_id" ]; then
                print_error "Job ID required"
                echo "Usage: $0 watch-job <job_id>"
                exit 1
            fi
            
            print_header "Watching Job: $job_id"
            print_info "Press Ctrl+C to stop"
            echo ""
            
            while true; do
                status=$(curl -s "http://localhost:8000/subtitles/$job_id/status" | jq -r '.status')
                timestamp=$(date '+%H:%M:%S')
                
                echo -e "${timestamp}: Status = ${GREEN}${status}${NC}"
                
                if [ "$status" == "DONE" ] || [ "$status" == "FAILED" ]; then
                    echo ""
                    print_success "Job finished with status: $status"
                    echo ""
                    echo "Final status:"
                    curl -s "http://localhost:8000/subtitles/$job_id/status" | jq .
                    echo ""
                    echo "Events:"
                    curl -s "http://localhost:8000/subtitles/$job_id/events" | jq .
                    break
                fi
                
                sleep 2
            done
            ;;
            
        check-redis)
            local job_id=$2
            
            print_header "Checking Redis Data"
            
            if [ -z "$job_id" ]; then
                print_info "Listing all job keys..."
                docker exec get-my-subtitle-redis-1 redis-cli KEYS "job:*"
            else
                print_info "Checking job: $job_id"
                echo ""
                echo "Job data:"
                docker exec get-my-subtitle-redis-1 redis-cli GET "job:$job_id" | jq .
                echo ""
                echo "Event count:"
                docker exec get-my-subtitle-redis-1 redis-cli LLEN "job:events:$job_id"
                echo ""
                echo "Events:"
                docker exec get-my-subtitle-redis-1 redis-cli LRANGE "job:events:$job_id" 0 -1 | while read -r line; do
                    echo "$line" | jq . 2>/dev/null || echo "$line"
                done
            fi
            ;;
            
        check-rabbitmq)
            print_header "Checking RabbitMQ"
            
            print_info "Opening RabbitMQ Management UI..."
            print_info "URL: http://localhost:15672"
            print_info "Login: guest / guest"
            echo ""
            
            # Check exchange
            exchange_info=$(curl -s -u guest:guest http://localhost:15672/api/exchanges/%2F/subtitle.events)
            
            if echo "$exchange_info" | jq -e . > /dev/null 2>&1; then
                print_success "Exchange 'subtitle.events' exists"
                echo "$exchange_info" | jq '{name, type, durable}'
            else
                print_error "Exchange 'subtitle.events' not found"
            fi
            
            echo ""
            
            # Check queue
            queue_info=$(curl -s -u guest:guest http://localhost:15672/api/queues/%2F/subtitle.events.consumer)
            
            if echo "$queue_info" | jq -e . > /dev/null 2>&1; then
                print_success "Queue 'subtitle.events.consumer' exists"
                echo "$queue_info" | jq '{name, messages, consumers, state}'
            else
                print_error "Queue 'subtitle.events.consumer' not found"
            fi
            
            echo ""
            print_info "Open full UI: open http://localhost:15672"
            ;;
            
        load-test)
            local count=${2:-5}
            
            print_header "Load Test: Submitting $count Jobs"
            
            declare -a job_ids
            
            for i in $(seq 1 $count); do
                print_info "Submitting job $i/$count..."
                
                response=$(curl -s -X POST http://localhost:8000/subtitles/download \
                    -H "Content-Type: application/json" \
                    -d "{
                        \"video_url\": \"https://example.com/load-test-$i.mp4\",
                        \"video_title\": \"Load Test Video $i\",
                        \"language\": \"he\",
                        \"preferred_sources\": [\"opensubtitles\"]
                    }")
                
                job_id=$(echo "$response" | jq -r '.job_id')
                job_ids+=("$job_id")
                print_success "Job $i submitted: $job_id"
            done
            
            echo ""
            print_header "Monitoring Jobs"
            
            # Wait for all jobs to complete
            all_done=false
            while [ "$all_done" = false ]; do
                all_done=true
                
                for job_id in "${job_ids[@]}"; do
                    status=$(curl -s "http://localhost:8000/subtitles/$job_id/status" | jq -r '.status')
                    
                    if [ "$status" != "DONE" ] && [ "$status" != "FAILED" ]; then
                        all_done=false
                    fi
                    
                    echo -e "Job $job_id: ${GREEN}${status}${NC}"
                done
                
                if [ "$all_done" = false ]; then
                    echo ""
                    sleep 3
                fi
            done
            
            echo ""
            print_success "All jobs completed!"
            
            # Summary
            echo ""
            print_header "Summary"
            
            for job_id in "${job_ids[@]}"; do
                status=$(curl -s "http://localhost:8000/subtitles/$job_id/status" | jq -r '.status')
                events=$(curl -s "http://localhost:8000/subtitles/$job_id/events" | jq -r '.event_count')
                
                if [ "$status" == "DONE" ]; then
                    print_success "Job $job_id: $status ($events events)"
                else
                    print_error "Job $job_id: $status ($events events)"
                fi
            done
            ;;
            
        view-logs)
            local service=$2
            
            print_header "Viewing Logs"
            
            if [ -z "$service" ]; then
                print_info "Viewing all logs (Ctrl+C to stop)..."
                docker-compose logs -f
            else
                print_info "Viewing $service logs (Ctrl+C to stop)..."
                docker-compose logs -f "$service"
            fi
            ;;
            
        clean)
            print_header "Cleaning Up"
            
            print_info "Stopping services..."
            docker-compose down -v
            
            print_info "Removing logs..."
            rm -rf logs/*
            
            print_success "Cleanup complete!"
            ;;
            
        restart)
            print_header "Restarting Services"
            
            docker-compose down
            docker-compose up -d
            
            print_info "Waiting for services to be healthy..."
            sleep 10
            
            $0 check-health
            ;;
            
        help|*)
            echo "Manual Testing Helper Script"
            echo ""
            echo "Usage: $0 <command> [arguments]"
            echo ""
            echo "Commands:"
            echo "  check-health              - Check if all services are healthy"
            echo "  submit-job [url] [title]  - Submit a test job"
            echo "  check-job <job_id>        - Check job status and events"
            echo "  watch-job <job_id>        - Watch job progress until done"
            echo "  check-redis [job_id]      - Check Redis data (all jobs or specific job)"
            echo "  check-rabbitmq            - Check RabbitMQ status"
            echo "  load-test [count]         - Submit multiple jobs (default: 5)"
            echo "  view-logs [service]       - View logs (all or specific service)"
            echo "  clean                     - Clean up all data"
            echo "  restart                   - Restart all services"
            echo "  help                      - Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 check-health"
            echo "  $0 submit-job 'https://example.com/video.mp4' 'My Video'"
            echo "  $0 watch-job 550e8400-e29b-41d4-a716-446655440000"
            echo "  $0 load-test 10"
            echo "  $0 view-logs consumer"
            ;;
    esac
}

# Run main function
main "$@"

