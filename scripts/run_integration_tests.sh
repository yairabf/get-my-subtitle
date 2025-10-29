#!/bin/bash
# Script to run integration tests for queue publishing with RabbitMQ

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=====================================${NC}"
echo -e "${YELLOW}Queue Publishing Integration Tests${NC}"
echo -e "${YELLOW}=====================================${NC}"
echo ""

# Change to project root directory
cd "$(dirname "$0")/.."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    exit 1
fi

# Function to check if RabbitMQ is healthy
check_rabbitmq_health() {
    local max_retries=30
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        if docker exec get-my-subtitle-rabbitmq-1 rabbitmq-diagnostics ping &> /dev/null; then
            echo -e "${GREEN}✓ RabbitMQ is healthy${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 1
        retry_count=$((retry_count + 1))
    done

    echo -e "${RED}✗ RabbitMQ failed to become healthy${NC}"
    return 1
}

# Start RabbitMQ container
echo -e "${YELLOW}Starting RabbitMQ container...${NC}"
docker-compose up -d rabbitmq

# Wait for RabbitMQ to be ready
echo -e "${YELLOW}Waiting for RabbitMQ to be ready${NC}"
if ! check_rabbitmq_health; then
    echo -e "${RED}Failed to start RabbitMQ${NC}"
    docker-compose logs rabbitmq
    exit 1
fi

echo ""
echo -e "${YELLOW}Running integration tests...${NC}"
echo ""

# Set environment variables for tests
export RABBITMQ_URL="amqp://guest:guest@localhost:5672/"
export REDIS_URL="redis://localhost:6379"

# Run integration tests
if pytest tests/integration/ -v -m integration --tb=short; then
    echo ""
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}✓ All integration tests passed!${NC}"
    echo -e "${GREEN}=====================================${NC}"
    exit_code=0
else
    echo ""
    echo -e "${RED}=====================================${NC}"
    echo -e "${RED}✗ Some integration tests failed${NC}"
    echo -e "${RED}=====================================${NC}"
    exit_code=1
fi

# Optional: Stop RabbitMQ after tests
# Uncomment if you want to automatically stop RabbitMQ
# echo ""
# echo -e "${YELLOW}Stopping RabbitMQ container...${NC}"
# docker-compose down rabbitmq

exit $exit_code

