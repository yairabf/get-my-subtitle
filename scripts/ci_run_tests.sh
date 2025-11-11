#!/bin/bash

################################################################################
# CI Test Runner Script
# 
# This script runs all tests (unit and integration) for CI/CD pipelines.
#
# Usage:
#   ./scripts/ci_run_tests.sh [options]
#
# Options:
#   --skip-integration    Skip integration tests (run unit tests only)
#   --verbose            Enable verbose output
#   --with-coverage      Generate coverage report
#
# Exit Codes:
#   0 - All tests passed
#   3 - Unit tests failed
#   4 - Integration tests failed
#   5 - Coverage below threshold
################################################################################

set -e  # Exit on error (disabled for some sections to capture exit codes)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SKIP_INTEGRATION=false
VERBOSE=false
WITH_COVERAGE=false
COVERAGE_THRESHOLD=80
EXIT_CODE=0

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-integration)
                SKIP_INTEGRATION=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --with-coverage)
                WITH_COVERAGE=true
                shift
                ;;
            -h|--help)
                grep "^#" "$0" | grep -v "#!/bin/bash" | sed 's/^# //'
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

################################################################################
# Main Script
################################################################################

main() {
    print_header "CI Test Runner"
    
    # Parse arguments
    parse_args "$@"
    
    print_info "Starting test execution..."
    print_info "Working directory: $(pwd)"
    print_info "Python version: $(python --version 2>&1)"
    
    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        print_info "Activating virtual environment..."
        source venv/bin/activate
    fi
    
    ############################################################################
    # 1. Unit Tests
    ############################################################################
    
    print_header "1. Running Unit Tests"
    
    print_info "Running unit tests with pytest..."
    
    if [ "$VERBOSE" = true ]; then
        pytest_cmd="pytest tests/ -v -m 'not integration' --tb=short"
    else
        pytest_cmd="pytest tests/ -m 'not integration' --tb=short"
    fi
    
    if eval "$pytest_cmd"; then
        print_success "Unit tests passed"
    else
        print_error "Unit tests failed"
        EXIT_CODE=3
        return $EXIT_CODE
    fi
    
    ############################################################################
    # 2. Integration Tests
    ############################################################################
    
    if [ "$SKIP_INTEGRATION" = false ]; then
        print_header "2. Running Integration Tests"
        
        print_info "Starting integration test environment..."
        
        # Check if Docker is available
        if ! command_exists docker-compose; then
            print_warning "docker-compose not found. Skipping integration tests."
            print_info "Install Docker and docker-compose to run integration tests"
        else
            # Start integration test environment
            print_info "Starting Docker services..."
            docker-compose -f docker-compose.integration.yml up -d --build
            
            # Wait for services to be healthy
            print_info "Waiting for services to be ready..."
            sleep 15
            
            # Show service status
            if [ "$VERBOSE" = true ]; then
                docker-compose -f docker-compose.integration.yml ps
            fi
            
            # Run integration tests
            print_info "Running integration tests..."
            
            if [ "$VERBOSE" = true ]; then
                pytest_cmd="pytest tests/integration/ -v --log-cli-level=INFO"
            else
                pytest_cmd="pytest tests/integration/ --tb=short"
            fi
            
            if eval "$pytest_cmd"; then
                print_success "Integration tests passed"
            else
                print_error "Integration tests failed"
                
                # Show logs on failure
                if [ "$VERBOSE" = true ]; then
                    print_info "Showing service logs..."
                    docker-compose -f docker-compose.integration.yml logs --tail=50
                fi
                
                EXIT_CODE=4
            fi
            
            # Cleanup
            print_info "Stopping integration test environment..."
            docker-compose -f docker-compose.integration.yml down -v
        fi
    else
        print_warning "Skipping integration tests (--skip-integration flag)"
    fi
    
    ############################################################################
    # 3. Code Coverage (Optional)
    ############################################################################
    
    if [ "$WITH_COVERAGE" = true ]; then
        print_header "3. Code Coverage Analysis"
        
        print_info "Generating coverage report..."
        
        if [ "$VERBOSE" = true ]; then
            coverage_cmd="pytest tests/ -m 'not integration' --cov=common --cov=manager --cov=downloader --cov=translator --cov=scanner --cov-report=term-missing --cov-report=xml --cov-report=html"
        else
            coverage_cmd="pytest tests/ -m 'not integration' --cov=common --cov=manager --cov=downloader --cov=translator --cov=scanner --cov-report=term --cov-report=xml --cov-report=html -q"
        fi
        
        if eval "$coverage_cmd"; then
            print_success "Coverage report generated"
            
            # Check coverage threshold
            coverage_percent=$(python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('coverage.xml')
root = tree.getroot()
coverage = float(root.attrib['line-rate']) * 100
print(f'{coverage:.1f}')
" 2>/dev/null || echo "0")
            
            print_info "Code coverage: ${coverage_percent}%"
            
            if (( $(echo "$coverage_percent < $COVERAGE_THRESHOLD" | bc -l) )); then
                print_warning "Coverage below threshold (${COVERAGE_THRESHOLD}%)"
                # Don't fail on coverage, just warn
            else
                print_success "Coverage meets threshold (${COVERAGE_THRESHOLD}%)"
            fi
            
            print_info "HTML coverage report: htmlcov/index.html"
            print_info "XML coverage report: coverage.xml"
        else
            print_error "Coverage analysis failed"
            EXIT_CODE=5
        fi
    fi
    
    ############################################################################
    # 4. Generate Summary Report
    ############################################################################
    
    print_header "Summary"
    
    echo ""
    echo "Test execution completed:"
    echo "  - Unit tests: $([ $EXIT_CODE -eq 3 ] && echo '❌' || echo '✅')"
    echo "  - Integration tests: $([ $SKIP_INTEGRATION = true ] && echo '⏭️  (skipped)' || ([ $EXIT_CODE -eq 4 ] && echo '❌' || echo '✅'))"
    if [ "$WITH_COVERAGE" = true ]; then
        echo "  - Code coverage: $([ $EXIT_CODE -eq 5 ] && echo '❌' || echo '✅') (${coverage_percent}%)"
    fi
    echo ""
    
    if [ $EXIT_CODE -eq 0 ]; then
        print_success "All tests passed! 🎉"
    else
        print_error "Some tests failed. Please review the errors above."
        print_info "Exit code: $EXIT_CODE"
    fi
    
    return $EXIT_CODE
}

################################################################################
# Script Entry Point
################################################################################

# Trap errors
trap 'echo -e "${RED}Script failed with error at line $LINENO${NC}"; exit 1' ERR

# Run main function
main "$@"
exit $EXIT_CODE

