#!/bin/bash
# Initiate a manual scan of the media library

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${YELLOW}Initiating manual scan...${NC}"

# Check if manager is running
if ! nc -z localhost 8000 2>/dev/null; then
    echo -e "${RED}❌ Manager API is not running on port 8000${NC}"
    echo "Start it with: ./run-worker.sh manager"
    exit 1
fi

# Trigger scan
response=$(curl -s -X POST http://localhost:8000/scan \
    -H "Content-Type: application/json" \
    -w "\nHTTP_CODE:%{http_code}")

http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "202" ] || [ "$http_code" == "200" ]; then
    echo -e "${GREEN}✅ Scan initiated successfully!${NC}"
    echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
else
    echo -e "${RED}❌ Failed to initiate scan (HTTP $http_code)${NC}"
    echo "$body"
    exit 1
fi

echo -e "\n${YELLOW}Monitor the scan progress with:${NC}"
echo "  ./monitor-workers.sh"








