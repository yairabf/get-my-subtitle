# GitHub Actions Setup Checklist

Use this checklist to ensure your CI/CD pipeline is properly configured.

## 📋 Initial Setup (One-Time)

### 1. GitHub Actions Configuration

- [ ] **Enable GitHub Actions**
  - Go to: `Settings` → `Actions` → `General`
  - Select: "Allow all actions and reusable workflows"
  - Click: `Save`

- [ ] **Configure Workflow Permissions**
  - Go to: `Settings` → `Actions` → `General`
  - Under "Workflow permissions":
    - Select: "Read and write permissions"
    - Check: "Allow GitHub Actions to create and approve pull requests"
  - Click: `Save`

### 2. Codecov Integration (Optional but Recommended)

- [ ] **Sign up for Codecov**
  - Visit: https://codecov.io
  - Sign in with GitHub account
  - Authorize Codecov

- [ ] **Add Repository to Codecov**
  - Find your repository in Codecov
  - Copy the upload token

- [ ] **Add Codecov Secret to GitHub**
  - Go to: `Settings` → `Secrets and variables` → `Actions`
  - Click: `New repository secret`
  - Name: `CODECOV_TOKEN`
  - Value: Paste the token from Codecov
  - Click: `Add secret`

### 3. Update Repository-Specific Information

- [ ] **Update README.md badges**
  ```bash
  # Replace 'yairabramovitch' with your GitHub username in README.md
  # Lines 3-7 contain the badges
  ```

- [ ] **Update Dependabot reviewer**
  ```yaml
  # Edit .github/dependabot.yml
  # Replace 'yairabramovitch' with your GitHub username
  # In the 'reviewers' section
  ```

### 4. Configure Branch Protection

#### For `main` branch:

- [ ] **Create Branch Protection Rule**
  - Go to: `Settings` → `Branches` → `Add rule`
  - Branch name pattern: `main`

- [ ] **Require Status Checks**
  - Check: "Require status checks to pass before merging"
  - Check: "Require branches to be up to date before merging"
  - Search and select these checks:
    - `CI Status Check`
    - `Check Black Formatting`
    - `Check Import Sorting`
    - `Unit Tests (Python 3.11)`
    - `Test Coverage`
    - `Integration Tests`
    - `Build Check`

- [ ] **Require Pull Request Reviews**
  - Check: "Require a pull request before merging"
  - Check: "Require approvals" → Set to: `1`
  - Check: "Dismiss stale pull request approvals when new commits are pushed"
  - Check: "Require review from Code Owners" (if using CODEOWNERS)

- [ ] **Additional Settings**
  - Check: "Require conversation resolution before merging"
  - Check: "Require signed commits" (optional)
  - Check: "Require linear history" (optional)
  - Check: "Include administrators" (optional)
  - Uncheck: "Allow force pushes"
  - Uncheck: "Allow deletions"

- [ ] **Save Protection Rule**
  - Click: `Create` or `Save changes`

#### For `develop` branch:

- [ ] **Repeat the same steps for `develop` branch**
  - You may want slightly relaxed rules for develop
  - Consider requiring fewer approvals (0 or 1)
  - Still require all CI checks to pass

## ✅ Verification Steps

### 1. Test CI Workflows

- [ ] **Create test branch**
  ```bash
  git checkout -b test/ci-verification
  echo "# CI Test" >> TEST_CI.md
  git add TEST_CI.md
  git commit -m "test: verify CI setup"
  git push origin test/ci-verification
  ```

- [ ] **Verify workflows run**
  - Go to: `Actions` tab
  - Check that both `CI` and `Lint` workflows started
  - Wait for completion
  - Verify all jobs passed ✅

- [ ] **Check workflow details**
  - Click on workflow run
  - Verify all jobs completed:
    - Lint
    - Unit Tests (Python 3.11 and 3.12)
    - Coverage
    - Integration Tests
    - Build Check
    - Status Check

### 2. Test Pull Request Flow

- [ ] **Create test PR**
  - On GitHub, create PR from `test/ci-verification` to `develop`
  - Add title: "test: CI verification"

- [ ] **Verify PR checks**
  - Check that required status checks appear
  - Verify CI runs automatically
  - Check for coverage comment (if Codecov is configured)

- [ ] **Verify branch protection**
  - Try to merge before CI completes (should be blocked)
  - Wait for CI to complete
  - Verify merge button becomes available

- [ ] **Clean up test**
  - Close the PR (don't merge)
  - Delete test branch:
    ```bash
    git checkout develop
    git branch -D test/ci-verification
    git push origin --delete test/ci-verification
    rm TEST_CI.md
    ```

### 3. Test Dependabot

- [ ] **Verify Dependabot is enabled**
  - Go to: `Insights` → `Dependency graph` → `Dependabot`
  - Check that Dependabot is active

- [ ] **Check for initial PRs**
  - Dependabot may create PRs for outdated dependencies
  - These should appear within a few hours

### 4. Test Local Development Workflow

- [ ] **Test make commands**
  ```bash
  make format    # Should format code
  make lint      # Should check formatting
  make test-unit # Should run tests
  make test-cov  # Should generate coverage
  make check     # Should run all checks
  ```

- [ ] **Verify all commands work without errors**

## 📚 Documentation Review

- [ ] **Read documentation files**
  - [ ] `.github/workflows/README.md` - Workflow details
  - [ ] `.github/SETUP_CI.md` - Detailed setup guide
  - [ ] `.github/CI_CD_SUMMARY.md` - Implementation overview
  - [ ] `.github/CI_QUICK_REFERENCE.md` - Quick reference
  - [ ] `GITHUB_ACTIONS_IMPLEMENTATION.md` - Full implementation details

- [ ] **Share with team**
  - Share `CI_QUICK_REFERENCE.md` with all developers
  - Ensure everyone knows to run `make check` before pushing

## 🎯 Optional Enhancements

### GitHub Features

- [ ] **Enable Discussions** (optional)
  - Go to: `Settings` → `General` → `Features`
  - Check: "Discussions"

- [ ] **Configure Code Owners** (optional)
  - Create `.github/CODEOWNERS` file
  - Define owners for different paths

- [ ] **Set up GitHub Projects** (optional)
  - Create project boards for issue tracking

### Additional Integrations

- [ ] **Add additional status badges to README**
  - Security scanning (Snyk)
  - Dependency status
  - License badge
  - Last commit badge

- [ ] **Set up Notifications**
  - Configure Slack/Discord webhooks for CI failures
  - Set up email notifications for important events

- [ ] **Configure Security**
  - Enable Dependabot security updates
  - Enable CodeQL analysis
  - Configure secret scanning

## 🔄 Regular Maintenance Checklist

### Weekly

- [ ] Review Dependabot PRs
- [ ] Check for failed workflow runs
- [ ] Verify CI runtime is acceptable (< 10 minutes)

### Monthly

- [ ] Review coverage trends
- [ ] Update Python versions if new release
- [ ] Review and update linting rules
- [ ] Check workflow optimization opportunities

### Quarterly

- [ ] Review branch protection rules
- [ ] Update documentation if needed
- [ ] Review CI/CD metrics and performance
- [ ] Plan improvements and optimizations

## 🆘 Troubleshooting

If something doesn't work:

1. **Check the logs**
   - Go to `Actions` tab
   - Click on failed workflow
   - Review job logs for errors

2. **Verify permissions**
   - Ensure Actions have read/write permissions
   - Check that secrets are set correctly

3. **Review documentation**
   - Check `.github/SETUP_CI.md` for common issues
   - Look at `.github/workflows/README.md` for workflow details

4. **Test locally**
   - Run `make check` to verify code passes locally
   - Check that all dependencies are installed

5. **Ask for help**
   - Create an issue with `ci/cd` label
   - Share workflow logs
   - Describe what you've tried

## ✨ Success Criteria

Your setup is complete when:

- ✅ All workflows run successfully
- ✅ Branch protection prevents merging failing PRs
- ✅ Coverage reports are generated (if Codecov configured)
- ✅ Dependabot creates update PRs
- ✅ Developers can run `make check` locally
- ✅ Documentation is accessible and clear
- ✅ Team understands the CI/CD process

## 🎉 You're Done!

Once you've checked off all required items, your CI/CD pipeline is ready to use!

### Next Steps

1. **Communicate to team**: Share documentation links
2. **Monitor first week**: Watch for any issues or confusion
3. **Iterate**: Improve based on team feedback
4. **Celebrate**: You've implemented a robust CI/CD pipeline! 🎊

---

**Need Help?** Check:
- [Detailed Setup Guide](.github/SETUP_CI.md)
- [Quick Reference](.github/CI_QUICK_REFERENCE.md)
- [Full Documentation](.github/workflows/README.md)
- [Implementation Details](../GITHUB_ACTIONS_IMPLEMENTATION.md)

