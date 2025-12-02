#!/bin/bash
# Helper script to run workers locally for debugging

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the worker name from command line
WORKER=${1:-}

if [ -z "$WORKER" ]; then
    echo -e "${RED}Usage: ./run-worker.sh <worker_name>${NC}"
    echo ""
    echo "Available workers:"
    echo "  - manager    (API server)"
    echo "  - downloader (Downloads subtitles)"
    echo "  - translator (Translates subtitles)"
    echo "  - consumer   (Processes events)"
    echo "  - scanner    (Monitors media files)"
    echo ""
    exit 1
fi

# Check if infrastructure is running
echo -e "${YELLOW}Checking infrastructure...${NC}"
if ! nc -z localhost 6379 2>/dev/null; then
    echo -e "${RED}❌ Redis is not accessible on localhost:6379${NC}"
    echo "Start it with: docker-compose up -d redis"
    exit 1
fi

if ! nc -z localhost 5672 2>/dev/null; then
    echo -e "${RED}❌ RabbitMQ is not accessible on localhost:5672${NC}"
    echo "Start it with: docker-compose up -d rabbitmq"
    exit 1
fi

echo -e "${GREEN}✅ Infrastructure is running${NC}"
echo ""

# Change to project root
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# Set PYTHONPATH to include src directory for imports
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH}"

# Detect Python command (prefer python3, fallback to python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Python not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Run the appropriate worker
case $WORKER in
    manager)
        echo -e "${GREEN}🚀 Starting Manager (API Server)...${NC}"
        cd src/manager
        $PYTHON_CMD main.py
        ;;
    downloader)
        echo -e "${GREEN}🚀 Starting Downloader Worker...${NC}"
        cd src/downloader
        $PYTHON_CMD worker.py
        ;;
    translator)
        echo -e "${GREEN}🚀 Starting Translator Worker...${NC}"
        cd src/translator
        $PYTHON_CMD worker.py
        ;;
    consumer)
        echo -e "${GREEN}🚀 Starting Consumer Worker...${NC}"
        cd src/consumer
        $PYTHON_CMD worker.py
        ;;
    scanner)
        echo -e "${GREEN}🚀 Starting Scanner Service...${NC}"
        cd src/scanner
        $PYTHON_CMD worker.py
        ;;
    *)
        echo -e "${RED}❌ Unknown worker: $WORKER${NC}"
        echo "Available workers: manager, downloader, translator, consumer, scanner"
        exit 1
        ;;
esac

