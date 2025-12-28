# Israel Transportation Integration - Release Preparation

Comprehensive pre-release validation and automated release workflow for the Israel Transportation (Silent Bus) integration.

## Usage

- `/hass-release-prep` - Full release validation and guidance
- `/hass-release-prep --version 1.4.0` - Prepare specific version for release
- `/hass-release-prep --check-only` - Only run checks, don't create tag
- `/hass-release-prep --publish` - Create tag and trigger release

## Smart Release Workflow

### Phase 1: Pre-Release Analysis

```bash
# Check current state
git status
git log --oneline -5

# Get current version
python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['version'])"

# Check GitHub Actions status
gh run list --limit 5
```

### Phase 2: Version Validation

```python
# Check version consistency across all files
import json

manifest_version = json.load(open('custom_components/silent_bus/manifest.json'))['version']

# Check CHANGELOG has entry
with open('CHANGELOG.md') as f:
    if f'## [{manifest_version}]' in f.read():
        print(f"CHANGELOG has entry for {manifest_version}")
    else:
        print(f"WARNING: Add CHANGELOG entry for {manifest_version}")
```

### Phase 3: Quality Gates

All must pass before release:

| Gate | Command | Required |
|------|---------|----------|
| Pre-commit | `pre-commit run --all-files` | Pass |
| Tests | `pytest -v` | All pass |
| hassfest | GitHub Actions | Pass |
| HACS | GitHub Actions | Pass |
| Git clean | `git status --porcelain` | Empty |

### Phase 4: Release Creation

```bash
# Get version from manifest
VERSION=$(python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['version'])")
echo "Releasing version: $VERSION"

# Ensure on main branch
git checkout main
git pull origin main

# Create and push tag
git tag v$VERSION
git push origin v$VERSION

# Monitor release workflow
gh run watch
```

## Version Bump Guide

### When to Bump

| Change Type | Version Part | Example |
|-------------|--------------|---------|
| Breaking change | MAJOR | 1.0.0 → 2.0.0 |
| New feature | MINOR | 1.3.0 → 1.4.0 |
| Bug fix | PATCH | 1.3.2 → 1.3.3 |

### Version Bump Procedure

1. **Update manifest.json:**
```json
{
  "version": "1.4.0"
}
```

2. **Update CHANGELOG.md:**
```markdown
## [1.4.0] - 2025-12-28

### Added
- New feature description

### Fixed
- Bug fix description

### Changed
- Change description
```

3. **Commit and push:**
```bash
git add custom_components/silent_bus/manifest.json CHANGELOG.md
git commit -m "Bump version to 1.4.0"
git push
```

## Release Checklist

### Pre-Release

- [ ] **Version bumped** in `manifest.json`
- [ ] **CHANGELOG updated** with new version section
- [ ] **Pre-commit passes:** `pre-commit run --all-files`
- [ ] **Tests pass:** `pytest -v`
- [ ] **CI passing:** Check GitHub Actions
  - [ ] hassfest workflow
  - [ ] HACS workflow
  - [ ] Tests workflow
- [ ] **Git clean:** No uncommitted changes
- [ ] **On main branch:** `git branch --show-current`

### Release Steps

- [ ] **Create tag:** `git tag v1.4.0`
- [ ] **Push tag:** `git push origin v1.4.0`
- [ ] **Monitor publish workflow:** `gh run watch`
- [ ] **Verify release created:** `gh release view v1.4.0`

### Post-Release

- [ ] **Test HACS installation** in test HA instance
- [ ] **Verify integration loads** without errors
- [ ] **Monitor for issues** on GitHub

## Automated Release Workflow

The `publish.yaml` workflow triggers on version tags:

1. **Validates** version consistency
2. **Creates** zip archive of integration
3. **Creates** GitHub Release
4. **Attaches** zip to release
5. **Generates** release notes from CHANGELOG

## Troubleshooting

### Tag Already Exists

```bash
# Delete local tag
git tag -d v1.4.0

# Delete remote tag (careful!)
git push origin :v1.4.0

# Create new tag
git tag v1.4.0
git push origin v1.4.0
```

### Release Workflow Failed

```bash
# Check workflow logs
gh run view <run_id> --log-failed

# Common fixes:
# 1. Version mismatch - update manifest.json
# 2. Tests failing - fix tests first
# 3. Pre-commit failing - run pre-commit locally
```

### Wrong Version Released

If you release the wrong version:

1. Delete the GitHub release
2. Delete the tag (see above)
3. Fix the issue
4. Create new tag and release

## Current Release Status

Check latest release:
```bash
gh release list --limit 5
gh release view --latest
```

Check what would be released:
```bash
# Show changes since last tag
git log $(git describe --tags --abbrev=0)..HEAD --oneline

# Show files that would be in release
git diff --name-only $(git describe --tags --abbrev=0)..HEAD
```

## HACS Integration

After release:
1. HACS should automatically detect new version
2. Users see update notification
3. Update installs from GitHub Release zip

If HACS doesn't update:
- Verify `hacs.json` is correct
- Check release has zip attachment
- Wait for HACS cache refresh (~1 hour)

## Related Files

- `custom_components/silent_bus/manifest.json` - Version source
- `CHANGELOG.md` - Release notes
- `.github/workflows/publish.yaml` - Release automation
- `.github/workflows/hassfest.yaml` - Validation
- `.github/workflows/hacs.yaml` - HACS validation

## Documentation

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [HACS Publishing](https://hacs.xyz/docs/publish/start)
