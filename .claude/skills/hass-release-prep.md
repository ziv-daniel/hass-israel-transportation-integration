# Home Assistant Integration Release Preparation

Comprehensive pre-release validation and checklist generation for the Silent Bus integration.

## Usage

- `/hass-release-prep` - Full release validation and checklist
- `/hass-release-prep --version 1.3.0` - Prepare specific version for release
- `/hass-release-prep --check-only` - Only run checks, don't create tag

## What it does

1. Verifies version consistency across all files
2. Runs complete test suite with coverage
3. Validates integration with hassfest and HACS
4. Checks CHANGELOG.md has entry for the version
5. Verifies documentation URLs are correct
6. Ensures clean git working directory
7. Generates release checklist
8. Provides git tag creation instructions

## Commands executed

```bash
# Step 1: Check version consistency
MANIFEST_VERSION=$(python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['version'])")
echo "Manifest version: $MANIFEST_VERSION"

# Verify CHANGELOG has entry
grep -q "## \[$MANIFEST_VERSION\]" CHANGELOG.md && echo "✓ CHANGELOG updated" || echo "✗ CHANGELOG missing entry for $MANIFEST_VERSION"

# Step 2: Run all tests
pytest --cov=custom_components.silent_bus --cov-report=term-missing

# Step 3: Run pre-commit checks
pre-commit run --all-files

# Step 4: Validate manifest and HACS
python -c "import json; json.load(open('custom_components/silent_bus/manifest.json'))"
python -c "import json; json.load(open('hacs.json'))"

# Step 5: Check git status
git status --porcelain

# Step 6: Verify documentation URLs
DOCS_URL=$(python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['documentation'])")
ISSUES_URL=$(python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['issue_tracker'])")
echo "Documentation: $DOCS_URL"
echo "Issues: $ISSUES_URL"

# Step 7: Check for GitHub Actions workflow status (if gh CLI available)
gh run list --limit 5
```

## Release checklist

### Pre-Release Validation

- [ ] **Version updated in manifest.json**
  - Current version matches intended release version
  - Follows semantic versioning (MAJOR.MINOR.PATCH)

- [ ] **CHANGELOG.md updated**
  - New version section added
  - Changes categorized (Added, Enhanced, Fixed, etc.)
  - Release date set
  - All significant changes documented

- [ ] **All tests passing**
  - Unit tests: ✓
  - Integration tests: ✓
  - Coverage >= 90%: ✓

- [ ] **Code quality checks passing**
  - Pre-commit hooks: ✓
  - Ruff linting: ✓
  - No trailing whitespace: ✓
  - YAML/JSON valid: ✓

- [ ] **Validation passing**
  - hassfest validation: ✓
  - HACS validation: ✓
  - manifest.json valid: ✓
  - Translations complete: ✓

- [ ] **Documentation current**
  - README.md reflects new features
  - manifest.json URLs correct
  - Examples up to date

- [ ] **Git repository clean**
  - All changes committed
  - Working directory clean
  - On correct branch (main/master)

### Release Process

1. **Tag the release**
   ```bash
   git tag v{VERSION}
   git push origin v{VERSION}
   ```

2. **Verify GitHub Actions**
   - hassfest workflow passes
   - HACS workflow passes
   - Publish workflow creates release

3. **Verify release created**
   - GitHub release exists
   - Release notes generated
   - Integration zip attached

4. **Test HACS installation**
   - Add as custom repository
   - Install in test Home Assistant instance
   - Verify integration loads correctly

### Post-Release

- [ ] **Announce release**
  - GitHub Discussions (if enabled)
  - Home Assistant Community Forum
  - Update any external documentation

- [ ] **Monitor for issues**
  - Watch GitHub Issues for bug reports
  - Check GitHub Actions for any failures
  - Respond to user questions

## Version bumping guide

### Semantic Versioning

- **MAJOR** (1.0.0 → 2.0.0): Breaking changes, incompatible API changes
- **MINOR** (1.2.0 → 1.3.0): New features, backwards-compatible
- **PATCH** (1.2.3 → 1.2.4): Bug fixes, backwards-compatible

### Files to update

1. `custom_components/silent_bus/manifest.json`:
   ```json
   "version": "1.3.0"
   ```

2. `CHANGELOG.md`:
   ```markdown
   ## [1.3.0] - 2025-12-26

   ### Added
   - New feature description

   ### Fixed
   - Bug fix description
   ```

## Common issues

**Issue**: Version mismatch between manifest.json and CHANGELOG.md
**Solution**: Ensure both files have the same version number. The manifest.json version is the source of truth.

**Issue**: Tests failing before release
**Solution**: Fix all test failures before creating a release. Run `/hass-test-integration` to identify issues.

**Issue**: hassfest validation fails
**Solution**: Check GitHub Actions hassfest workflow for specific error messages. Common issues: missing required files, invalid manifest.json fields.

**Issue**: Git working directory not clean
**Solution**: Commit all changes before creating a release:
```bash
git add .
git commit -m "Prepare release v1.3.0"
git push
```

**Issue**: Tag already exists
**Solution**: If you need to move a tag:
```bash
git tag -d v1.3.0           # Delete local tag
git push origin :v1.3.0     # Delete remote tag
git tag v1.3.0              # Create new tag
git push origin v1.3.0      # Push new tag
```

## GitHub Actions workflows

### Publish Workflow

The `publish.yaml` workflow automatically:
1. Triggers on version tags (e.g., `v1.3.0`)
2. Verifies version consistency
3. Creates zip archive of integration
4. Creates GitHub Release
5. Attaches zip file to release
6. Generates release notes

### Workflow Status

Check workflow status:
```bash
gh run list --workflow=publish.yaml
gh run view <RUN_ID>
```

## Creating a release tag

```bash
# Ensure you're on main/master branch
git checkout main
git pull

# Verify version in manifest.json
VERSION=$(python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['version'])")
echo "Creating release for version: $VERSION"

# Create and push tag
git tag v$VERSION
git push origin v$VERSION

# Monitor GitHub Actions
gh run watch
```

## Related files

- `custom_components/silent_bus/manifest.json` - Version source of truth
- `CHANGELOG.md` - Release notes and version history
- `.github/workflows/publish.yaml` - Automated release creation
- `.github/workflows/hassfest.yaml` - Integration validation
- `.github/workflows/hacs.yaml` - HACS validation

## Documentation links

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [HACS Release Process](https://hacs.xyz/docs/publish/start)
