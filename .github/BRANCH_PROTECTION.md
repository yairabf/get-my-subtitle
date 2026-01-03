# Branch Protection Setup Guide

This guide explains how to set up branch protection rules for the `main` branch to ensure code quality and prevent accidental changes.

## Quick Setup (Automated)

The easiest way to set up branch protection is using the provided script:

```bash
# Make the script executable
chmod +x .github/setup-branch-protection.sh

# Run the script (dry-run first to see what will be done)
./.github/setup-branch-protection.sh --dry-run

# Apply the protection rules
./.github/setup-branch-protection.sh
```

### Prerequisites

1. **Install GitHub CLI**: https://cli.github.com/
   ```bash
   # macOS
   brew install gh
   
   # Linux
   # Follow instructions at https://cli.github.com/
   ```

2. **Authenticate with GitHub**:
   ```bash
   gh auth login
   ```

3. **Ensure you have admin access** to the repository

## Manual Setup (GitHub UI)

If you prefer to set up branch protection manually:

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Branches**
3. Click **Add rule** or edit the existing rule for `main`
4. Configure the following settings:

### Branch Protection Settings

#### Required Settings

- ✅ **Require a pull request before merging**
  - ✅ Require approvals: **1**
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners: (optional, enable if you have CODEOWNERS file)

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - ✅ Required status checks:
    - `CI Pipeline / Code Quality`
    - `CI Pipeline / Unit Tests (Python 3.11)`
    - `CI Pipeline / Unit Tests (Python 3.12)`
    - `CI Pipeline / Integration Tests`
    - `CI Pipeline / Docker Build Validation`
    - `CI Pipeline / Security Scan`
    - `CI Pipeline / CI Status`
    
    **Note**: Status check names must match exactly. To find the exact names:
    1. Create a test PR or check an existing PR
    2. Go to the **Checks** tab
    3. Copy the exact check names shown there

- ✅ **Require conversation resolution before merging**

- ✅ **Require linear history**

- ✅ **Include administrators** (enforce restrictions for administrators)

#### Restrictions

- ❌ **Do not allow force pushes**
- ❌ **Do not allow deletions**

#### Merge Options

- ✅ **Allow squash merging**
- ✅ **Allow rebase merging**
- ❌ **Do not allow merge commits**

## What These Rules Do

### Code Quality Enforcement

- **Status Checks**: All CI checks must pass before merging:
  - Code formatting (Black, isort)
  - Linting (Flake8)
  - Unit tests (Python 3.11 and 3.12)
  - Integration tests
  - Docker build validation
  - Security scans

- **Pull Request Reviews**: At least one approval required before merging

- **Up-to-date Branches**: PRs must be rebased/updated with the latest `main` before merging

### Safety Features

- **No Force Pushes**: Prevents rewriting history on the main branch
- **No Branch Deletion**: Protects against accidental deletion
- **Linear History**: Ensures clean, easy-to-follow git history
- **Conversation Resolution**: All PR comments must be resolved before merging

### Merge Strategy

- **Squash Merge**: Recommended for feature branches (creates clean history)
- **Rebase Merge**: Alternative option for maintaining linear history
- **Merge Commits**: Disabled to prevent merge commit clutter

## Testing Branch Protection

After setting up branch protection, test it by:

1. Creating a feature branch:
   ```bash
   git checkout -b test-branch-protection
   ```

2. Making a change and pushing:
   ```bash
   echo "# Test" >> TEST.md
   git add TEST.md
   git commit -m "Test branch protection"
   git push origin test-branch-protection
   ```

3. Creating a pull request to `main`

4. Try to merge without:
   - Running CI checks (should be blocked)
   - Getting approval (should be blocked)
   - Updating the branch (should be blocked if behind)

## Modifying Branch Protection

### Using the Script

To modify protection for a different branch:
```bash
./.github/setup-branch-protection.sh --branch develop
```

### Using GitHub CLI with JSON Template

A template JSON file is provided at `.github/branch-protection-template.json`:

```bash
# View current protection rules
gh api repos/:owner/:repo/branches/main/protection

# Update protection rules using the template
# First, update the status check names in the template to match your repository
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --input .github/branch-protection-template.json
```

**Important**: Before using the template, update the `contexts` array with the exact status check names from your repository (see "Finding Status Check Names" below).

### Using GitHub UI

1. Go to **Settings** → **Branches**
2. Click on the branch rule you want to modify
3. Update settings and click **Save changes**

## Finding Status Check Names

Status check names must match exactly. To find the correct names:

1. **From a Pull Request**:
   - Create or open a PR
   - Go to the **Checks** tab
   - Copy the exact check names (e.g., "CI Pipeline / Code Quality")

2. **Using GitHub API**:
   ```bash
   # Get all status checks for a branch
   gh api repos/:owner/:repo/commits/$(git rev-parse main)/statuses
   ```

3. **From GitHub UI**:
   - Go to **Settings** → **Branches**
   - When adding required checks, GitHub will show available checks in a dropdown

## Troubleshooting

### "Status checks are required but not found"

This happens when the required status checks haven't run yet. To fix:

1. Wait for the CI workflow to run at least once on a PR
2. Or manually trigger the workflow
3. The status check names will then be available in the branch protection settings

### "Cannot push to protected branch"

This is expected behavior. To make changes to `main`:

1. Create a feature branch
2. Make your changes
3. Create a pull request
4. Get approval and pass all checks
5. Merge via pull request

### "Required status check is not found"

If a status check name doesn't match:

1. Check the actual job names in `.github/workflows/ci.yml`
2. Update the branch protection settings to match the exact job names
3. Job names follow the pattern: `Workflow Name / Job Name`

## Additional Resources

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [CI/CD Workflows](../.github/workflows/README.md)

