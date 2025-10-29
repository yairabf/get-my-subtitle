# GitHub Actions CI/CD Setup Guide

This guide will help you set up and configure GitHub Actions for this project.

## Initial Setup

### 1. Enable GitHub Actions

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Actions** → **General**
3. Under "Actions permissions", select **"Allow all actions and reusable workflows"**
4. Under "Workflow permissions", select **"Read and write permissions"**
5. Check **"Allow GitHub Actions to create and approve pull requests"**
6. Click **Save**

### 2. Set Up Codecov (Optional but Recommended)

Codecov provides detailed coverage reports and visualizations.

#### Steps:

1. **Sign up for Codecov**
   - Visit [codecov.io](https://codecov.io)
   - Sign in with your GitHub account
   - Authorize Codecov to access your repositories

2. **Add Repository**
   - Find and add your `get-my-subtitle` repository
   - Codecov will provide a token

3. **Add Secret to GitHub**
   - Go to your repository on GitHub
   - Navigate to **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `CODECOV_TOKEN`
   - Value: Paste the token from Codecov
   - Click **Add secret**

### 3. Configure Branch Protection Rules

Protect your main branches to ensure code quality.

#### For `main` branch:

1. Go to **Settings** → **Branches** → **Add rule**
2. Branch name pattern: `main`
3. Configure the following:

   **Require status checks:**
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - Select these status checks:
     - `CI Status Check`
     - `Check Black Formatting`
     - `Check Import Sorting`
     - `Unit Tests (Python 3.11)`
     - `Test Coverage`

   **Require pull request reviews:**
   - ✅ Require a pull request before merging
   - ✅ Require approvals: 1
   - ✅ Dismiss stale pull request approvals when new commits are pushed

   **Additional settings:**
   - ✅ Require conversation resolution before merging
   - ✅ Require linear history (optional)
   - ✅ Do not allow bypassing the above settings

4. Click **Create**

#### For `develop` branch:

Repeat the same steps with branch name pattern: `develop`

### 4. Update Repository Information

Update the badge URLs in README.md with your GitHub username:

```markdown
[![CI](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/YOUR_USERNAME/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/get-my-subtitle)
```

Replace `YOUR_USERNAME` with your actual GitHub username.

### 5. Update Dependabot Configuration

Edit `.github/dependabot.yml` and update the reviewers section with your GitHub username:

```yaml
reviewers:
  - "your-github-username"
```

## Testing the Setup

### 1. Test Locally First

Before pushing, ensure everything works locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run formatting
make format

# Run linting
make lint

# Run tests
make test-unit

# Run coverage
make test-cov
```

### 2. Create a Test Branch

```bash
# Create a test branch
git checkout -b test/ci-setup

# Make a small change
echo "# CI Test" >> test_ci.txt
git add test_ci.txt
git commit -m "test: CI setup verification"

# Push to GitHub
git push origin test/ci-setup
```

### 3. Verify Workflows

1. Go to your repository on GitHub
2. Navigate to **Actions** tab
3. You should see workflows running
4. Check that all jobs complete successfully:
   - ✅ Lint
   - ✅ Unit Tests
   - ✅ Coverage
   - ✅ Integration Tests
   - ✅ Build Check

### 4. Create a Test Pull Request

1. On GitHub, create a pull request from `test/ci-setup` to `develop`
2. Verify that:
   - CI checks run automatically
   - Coverage report is posted as a comment
   - All required checks must pass
   - Branch protection prevents merging if checks fail

### 5. Clean Up

After verifying everything works:

```bash
# Delete test file
git checkout develop
git branch -D test/ci-setup
git push origin --delete test/ci-setup
rm test_ci.txt
```

## Troubleshooting

### Issue: Workflows Not Running

**Cause:** GitHub Actions might not be enabled or workflows have errors.

**Solution:**
1. Check that Actions are enabled in Settings
2. Verify YAML syntax is correct
3. Check workflow logs for errors

### Issue: Coverage Upload Failing

**Cause:** Missing or incorrect `CODECOV_TOKEN`.

**Solution:**
1. Verify the secret is set correctly in repository settings
2. Check that the token hasn't expired
3. Ensure Codecov has access to your repository

### Issue: Integration Tests Failing

**Cause:** Services not starting properly in GitHub Actions.

**Solution:**
1. Check service health checks in `ci.yml`
2. Verify service images are accessible
3. Check service logs in workflow runs

### Issue: Docker Build Failures

**Cause:** Dockerfile syntax errors or missing dependencies.

**Solution:**
1. Test Docker builds locally: `docker build -f manager/Dockerfile .`
2. Check Dockerfile for syntax errors
3. Verify all required files are present

### Issue: Branch Protection Preventing Merge

**Cause:** Required checks not completed or failed.

**Solution:**
1. Ensure all CI checks pass
2. Fix any failing tests or linting issues
3. Update branch with latest changes from base branch

## Monitoring and Maintenance

### 1. Monitor Workflow Runs

- Regularly check the **Actions** tab for failed workflows
- Set up notifications for workflow failures
- Review and act on Dependabot pull requests

### 2. Update Dependencies

When Dependabot creates PRs:
1. Review the changes
2. Check if tests pass
3. Merge if everything looks good

### 3. Adjust Coverage Thresholds

If needed, adjust coverage requirements in `ci.yml`:

```yaml
--cov-fail-under=70  # Change this value
```

### 4. Optimize Workflow Performance

Monitor workflow run times and optimize as needed:
- Use caching effectively
- Parallelize independent jobs
- Minimize dependencies in lint jobs

## Advanced Configuration

### Adding New Required Checks

1. Edit `.github/workflows/ci.yml` or create new workflow
2. Add the check to branch protection rules
3. Update documentation

### Custom Linting Rules

Edit `.pylintrc` to customize Pylint behavior:

```ini
[MESSAGES CONTROL]
disable=
    C0111,  # Add more disabled checks
```

### Matrix Testing

Add more Python versions or operating systems in `ci.yml`:

```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12', '3.13']
    os: [ubuntu-latest, macos-latest]
```

## Best Practices

1. **Always test locally before pushing**
   ```bash
   make check
   ```

2. **Keep workflows fast**
   - Use caching
   - Run only necessary tests
   - Parallelize where possible

3. **Monitor coverage trends**
   - Don't let coverage drop
   - Add tests for new features
   - Review coverage reports regularly

4. **Keep dependencies updated**
   - Review Dependabot PRs promptly
   - Test thoroughly before merging
   - Keep an eye on security advisories

5. **Document changes**
   - Update README when adding workflows
   - Comment complex workflow logic
   - Keep this guide up to date

## Getting Help

- **GitHub Actions Documentation**: https://docs.github.com/en/actions
- **Codecov Documentation**: https://docs.codecov.com/
- **pytest Documentation**: https://docs.pytest.org/
- **Black Documentation**: https://black.readthedocs.io/
- **isort Documentation**: https://pycqa.github.io/isort/

## Next Steps

After setting up CI/CD:

1. ✅ Verify all workflows run successfully
2. ✅ Set up branch protection on `main` and `develop`
3. ✅ Configure Codecov integration
4. ✅ Update README badges with your repository URL
5. ✅ Set up notifications for workflow failures
6. ✅ Review and merge Dependabot PRs regularly
7. ✅ Train team members on the CI/CD process

---

**Note:** This setup ensures code quality and prevents breaking changes from being merged. All changes must pass automated tests and code quality checks before being merged to protected branches.

