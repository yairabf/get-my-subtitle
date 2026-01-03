#!/bin/bash

################################################################################
# GitHub Branch Protection Setup Script
# 
# This script sets up branch protection rules for the main branch.
# It requires the GitHub CLI (gh) to be installed and authenticated.
#
# Usage:
#   ./setup-branch-protection.sh [options]
#
# Options:
#   --branch <name>    Branch to protect (default: main)
#   --dry-run          Show what would be done without making changes
#   --help             Show this help message
#
# Prerequisites:
#   1. Install GitHub CLI: https://cli.github.com/
#   2. Authenticate: gh auth login
#   3. Ensure you have admin access to the repository
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BRANCH="main"
DRY_RUN=false
REPO_OWNER=""
REPO_NAME=""

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
            --branch)
                BRANCH="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
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

# Get repository information
get_repo_info() {
    if ! command_exists gh; then
        print_error "GitHub CLI (gh) is not installed."
        print_info "Install it from: https://cli.github.com/"
        exit 1
    fi
    
    if ! gh auth status &>/dev/null; then
        print_error "GitHub CLI is not authenticated."
        print_info "Run: gh auth login"
        exit 1
    fi
    
    # Get repo owner and name from git remote
    REPO_FULL=$(git remote get-url origin 2>/dev/null | sed -E 's/.*github.com[:/]([^/]+\/[^/]+)(\.git)?$/\1/' || echo "")
    
    if [ -z "$REPO_FULL" ]; then
        print_error "Could not determine repository from git remote."
        print_info "Make sure you're in a git repository with a 'origin' remote pointing to GitHub."
        exit 1
    fi
    
    REPO_OWNER=$(echo "$REPO_FULL" | cut -d'/' -f1)
    REPO_NAME=$(echo "$REPO_FULL" | cut -d'/' -f2)
    
    print_info "Repository: $REPO_OWNER/$REPO_NAME"
    print_info "Branch: $BRANCH"
    
    # Note about status check names
    print_warning "Note: Status check names must match exactly."
    print_info "To find exact names, check a recent PR's 'Checks' tab or run:"
    print_info "  gh api repos/$REPO_OWNER/$REPO_NAME/branches/$BRANCH/protection"
}

# Check if branch exists
check_branch_exists() {
    if ! git show-ref --verify --quiet refs/heads/"$BRANCH" && \
       ! git show-ref --verify --quiet refs/remotes/origin/"$BRANCH"; then
        print_error "Branch '$BRANCH' does not exist locally or remotely."
        exit 1
    fi
}

# Set up branch protection rules
setup_branch_protection() {
    print_header "Setting up branch protection for '$BRANCH'"
    
    if [ "$DRY_RUN" = true ]; then
        print_warning "DRY RUN MODE - No changes will be made"
        echo ""
    fi
    
    # Required status checks (from CI workflow)
    # These status check names must match the actual check names in GitHub
    # Format: "Workflow Name / Job Display Name"
    # Note: For matrix jobs, the name includes the matrix value
    # To find exact names: Go to a PR → Checks tab → See the exact check names
    REQUIRED_CHECKS=(
        "CI Pipeline / Code Quality"
        "CI Pipeline / Unit Tests (Python 3.11)"
        "CI Pipeline / Unit Tests (Python 3.12)"
        "CI Pipeline / Integration Tests"
        "CI Pipeline / Docker Build Validation"
        "CI Pipeline / Security Scan"
        "CI Pipeline / CI Status"
    )
    
    # Build the status check contexts string
    STATUS_CHECKS_JSON=$(printf '%s\n' "${REQUIRED_CHECKS[@]}" | jq -R . | jq -s .)
    
    # Branch protection settings
    PROTECTION_SETTINGS=$(cat <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": ${STATUS_CHECKS_JSON}
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true,
  "allow_squash_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": true,
  "required_conversation_resolution": true
}
EOF
)
    
    if [ "$DRY_RUN" = true ]; then
        print_info "Would apply the following branch protection settings:"
        echo "$PROTECTION_SETTINGS" | jq .
        echo ""
        print_info "To apply these settings, run without --dry-run"
    else
        print_info "Applying branch protection rules..."
        
        # Use gh API to update branch protection
        if echo "$PROTECTION_SETTINGS" | gh api \
            repos/"$REPO_OWNER"/"$REPO_NAME"/branches/"$BRANCH"/protection \
            --method PUT \
            --input -; then
            print_success "Branch protection rules applied successfully!"
        else
            print_error "Failed to apply branch protection rules."
            print_info "Make sure you have admin access to the repository."
            exit 1
        fi
    fi
}

# Display summary
display_summary() {
    print_header "Branch Protection Summary"
    
    echo "Branch: $BRANCH"
    echo ""
    echo "Protection Rules Applied:"
    echo "  ✅ Require status checks to pass before merging"
    echo "  ✅ Require branches to be up to date before merging"
    echo "  ✅ Require pull request reviews (1 approval required)"
    echo "  ✅ Dismiss stale pull request approvals when new commits are pushed"
    echo "  ✅ Require conversation resolution before merging"
    echo "  ✅ Enforce restrictions for administrators"
    echo "  ✅ Prevent force pushes"
    echo "  ✅ Prevent branch deletion"
    echo "  ✅ Require linear history"
    echo "  ✅ Allow squash merge"
    echo "  ✅ Allow rebase merge"
    echo "  ❌ Disallow merge commits"
    echo ""
    echo "Required Status Checks:"
    for check in "${REQUIRED_CHECKS[@]}"; do
        echo "  - $check"
    done
    echo ""
    print_warning "If status checks fail to match, find exact names in a PR's 'Checks' tab"
    echo ""
    print_info "You can view and modify these settings at:"
    print_info "https://github.com/$REPO_OWNER/$REPO_NAME/settings/branches"
}

################################################################################
# Main Script
################################################################################

main() {
    print_header "GitHub Branch Protection Setup"
    
    # Parse arguments
    parse_args "$@"
    
    # Get repository information
    get_repo_info
    
    # Check if branch exists
    check_branch_exists
    
    # Set up branch protection
    setup_branch_protection
    
    # Display summary
    if [ "$DRY_RUN" = false ]; then
        display_summary
    fi
    
    print_success "Setup complete!"
}

################################################################################
# Script Entry Point
################################################################################

# Check for jq (required for JSON processing)
if ! command_exists jq; then
    print_error "jq is required but not installed."
    print_info "Install it with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Run main function
main "$@"

