#!/bin/bash

################################################################################
# CI Code Quality Script
# 
# This script runs code quality checks ONLY (no tests).
# It performs linting, formatting checks, type checking, and security scanning.
#
# Usage:
#   ./scripts/ci_code_quality.sh [options]
#
# Options:
#   --verbose            Enable verbose output
#   --fail-fast          Stop on first failure
#
# Exit Codes:
#   0 - All checks passed
#   1 - Linting/formatting errors
#   2 - Type checking errors (non-blocking)
################################################################################

set -e  # Exit on error (disabled for some sections to capture exit codes)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VERBOSE=false
FAIL_FAST=false
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
            --verbose)
                VERBOSE=true
                shift
                ;;
            --fail-fast)
                FAIL_FAST=true
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

# Run command with optional verbosity
run_cmd() {
    local cmd="$1"
    local error_code="${2:-1}"
    
    if [ "$VERBOSE" = true ]; then
        eval "$cmd"
    else
        eval "$cmd" > /dev/null 2>&1
    fi
    
    local result=$?
    
    if [ $result -ne 0 ]; then
        EXIT_CODE=$error_code
        if [ "$FAIL_FAST" = true ]; then
            exit $EXIT_CODE
        fi
    fi
    
    return $result
}

################################################################################
# Main Script
################################################################################

main() {
    print_header "CI Code Quality Checks"
    
    # Parse arguments
    parse_args "$@"
    
    print_info "Starting code quality checks..."
    print_info "Working directory: $(pwd)"
    print_info "Python version: $(python --version 2>&1)"
    
    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        print_info "Activating virtual environment..."
        source venv/bin/activate
    fi
    
    ############################################################################
    # 1. Code Formatting Check (Black)
    ############################################################################
    
    print_header "1. Checking Code Formatting (Black)"
    
    if ! command_exists black; then
        print_warning "Black not found. Installing..."
        pip install black > /dev/null 2>&1
    fi
    
    if run_cmd "black --check --diff ." 1; then
        print_success "Code formatting check passed"
    else
        print_error "Code formatting check failed"
        print_info "Run 'make format' or 'black .' to fix formatting issues"
    fi
    
    ############################################################################
    # 2. Import Sorting Check (isort)
    ############################################################################
    
    print_header "2. Checking Import Sorting (isort)"
    
    if ! command_exists isort; then
        print_warning "isort not found. Installing..."
        pip install isort > /dev/null 2>&1
    fi
    
    if run_cmd "isort --check-only --diff ." 1; then
        print_success "Import sorting check passed"
    else
        print_error "Import sorting check failed"
        print_info "Run 'make format' or 'isort .' to fix import sorting"
    fi
    
    ############################################################################
    # 3. Linting (Flake8)
    ############################################################################
    
    print_header "3. Running Linter (Flake8)"
    
    if ! command_exists flake8; then
        print_warning "Flake8 not found. Installing..."
        pip install flake8 > /dev/null 2>&1
    fi
    
    if run_cmd "flake8 --max-line-length=120 --extend-ignore=E203,W503 ." 1; then
        print_success "Linting passed"
    else
        print_error "Linting failed"
        print_info "Fix linting errors shown above"
    fi
    
    ############################################################################
    # 4. Type Checking (MyPy) - Optional
    ############################################################################
    
    print_header "4. Type Checking (MyPy)"
    
    if command_exists mypy; then
        if run_cmd "mypy --ignore-missing-imports --no-strict-optional common/ manager/ scanner/ downloader/ translator/" 2; then
            print_success "Type checking passed"
        else
            print_warning "Type checking found issues (non-blocking)"
        fi
    else
        print_warning "MyPy not found. Skipping type checking."
        print_info "Install with: pip install mypy"
    fi
    
    ############################################################################
    # 5. Security Check (Bandit) - Optional
    ############################################################################
    
    print_header "5. Security Scanning (Bandit)"
    
    if command_exists bandit; then
        if run_cmd "bandit -r common/ manager/ scanner/ downloader/ translator/ -ll -f json -o bandit-report.json" 2; then
            print_success "Security scan passed"
        else
            print_warning "Security scan found issues (non-blocking)"
            print_info "Review bandit-report.json for details"
        fi
    else
        print_warning "Bandit not found. Skipping security scan."
        print_info "Install with: pip install bandit"
    fi
    
    ############################################################################
    # 6. Generate Summary Report
    ############################################################################
    
    print_header "Summary"
    
    echo ""
    echo "Code quality checks completed:"
    echo "  - Code formatting (Black): $([ $EXIT_CODE -eq 1 ] && echo '❌' || echo '✅')"
    echo "  - Import sorting (isort): $([ $EXIT_CODE -eq 1 ] && echo '❌' || echo '✅')"
    echo "  - Linting (Flake8): $([ $EXIT_CODE -eq 1 ] && echo '❌' || echo '✅')"
    echo "  - Type checking (MyPy): ⚠️  (non-blocking)"
    echo "  - Security scan (Bandit): ⚠️  (non-blocking)"
    echo ""
    
    if [ $EXIT_CODE -eq 0 ]; then
        print_success "All code quality checks passed! 🎉"
    else
        print_error "Some checks failed. Please fix the issues above."
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
