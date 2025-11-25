# Deployment Notes

## VERSION File Format

The `VERSION` file in the root directory contains the current version number and must follow these specifications:

- **Format**: Semantic versioning (e.g., `1.2.3`)
- **Encoding**: UTF-8
- **Newline**: **NO trailing newline** (canonical format)

### Why No Newline?

The release workflow (`/.github/workflows/release.yml`) explicitly writes the VERSION file without a trailing newline using PowerShell's `Set-Content -NoNewline`. This is the canonical format that all tooling expects.

The deploy-site workflow (`/.github/workflows/deploy-site.yml`) strips any newlines when reading the file, so it tolerates both formats, but the standard is without a newline.

## Website Deployment Workflow

The BindKit website (https://www.bindkit.com/) displays the latest version and is deployed via GitHub Actions.

### Deployment Triggers

The `deploy-site.yml` workflow deploys the website when:

1. **Push to main** with changes to:
   - `site/**` (website files)
   - `VERSION` (version file)
   - `.github/workflows/deploy-site.yml` (the workflow itself)

2. **GitHub Release published** event

### Version Injection

The deployment workflow reads the VERSION file and injects it into the website HTML by replacing the `__BINDKIT_VERSION__` placeholder.

## Known Issues

### November 2025 v1.2.2 Deployment Failure

On November 23, 2025, the v1.2.2 release was published but the website didn't update automatically. Investigation revealed:

1. The release workflow successfully created the GitHub release
2. The VERSION file was updated to `1.2.2`
3. The deploy-site workflow **failed to trigger** from either:
   - The push event (despite VERSION being modified)
   - The release published event

**Root Cause**: Unknown GitHub Actions issue - both triggers should have worked but neither fired.

**Resolution**: Manually triggered deployment by adding a newline to VERSION file and pushing the change.

**Prevention**: If this happens again:
1. Check workflow runs: `gh run list --workflow deploy-site.yml`
2. Manually trigger by making a trivial change to VERSION or site files
3. Consider adding `workflow_dispatch` trigger to deploy-site.yml for manual triggering

## Best Practices

1. **Always verify deployment** after a release by checking the website
2. **Monitor GitHub Actions** for both release and deploy-site workflows
3. **Keep VERSION format consistent** - no trailing newline
4. **Document any deployment issues** in this file for future reference