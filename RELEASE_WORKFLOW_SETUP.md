# Release Workflow Setup Guide

## ✅ What's Been Implemented

### Files Created

1. **`.publicignore`** - Exclusion patterns for private files
   - Excludes `.claude/`, `tests/`, `scripts/`, and other development files
   - Works like `.gitignore` for the sync process

2. **`.github/workflows/auto-beta-version.yml`** - Auto Beta Versioning
   - Triggers on every push to `main`
   - Auto-increments beta versions (e.g., `2.0.3-beta.1`, `2.0.3-beta.2`)
   - Creates pre-releases in private repo only
   - Allows testing without polluting stable version numbers

3. **`.github/workflows/release-to-public.yml`** - Public Release Sync
   - Triggers when you publish a stable release
   - Validates CI workflows passed
   - Syncs files to public repo (excluding private files)
   - Creates release in public repo with GTFS data assets
   - Supports version bump types: `[patch]` (default), `[minor]`, `[major]`

## 📋 Manual Setup Required

### Step 1: Create GitHub Personal Access Token (PAT)

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Name: `Private to Public Repo Sync`
4. Expiration: Choose appropriate duration (recommend: 1 year)
5. Scopes: Select **`repo`** (Full control of private repositories)
6. Click **"Generate token"**
7. **Copy the token immediately** (you won't see it again)

### Step 2: Add Secret to Private Repository

1. Go to: https://github.com/ziv-daniel/israel-bus-integration/settings/secrets/actions
2. Click **"New repository secret"**
3. Name: `PUBLIC_REPO_TOKEN`
4. Value: Paste the PAT token from Step 1
5. Click **"Add secret"**

### Step 3: (Optional) Reset Version Number

If you want to start with a more accurate version number:

```bash
# Edit manifest.json manually or use:
python scripts/bump_version.py 0.1.0-beta.1
git add custom_components/israel_transportation/manifest.json
git commit -m "chore: Reset version to 0.1.0-beta.1"
git push
```

## 🚀 How to Use

### Daily Development Workflow

1. **Make changes** and commit to `main` branch
2. **CI runs automatically** (test, hassfest, pre-commit)
3. **auto-beta-version.yml triggers:**
   - Bumps version to `X.Y.Z-beta.N`
   - Creates pre-release in private repo
4. **Test locally:**
   - Symlink to Home Assistant: `ln -s /path/to/custom_components/israel_transportation ~/.homeassistant/custom_components/`
   - OR use HACS custom repository pointing to private repo

### When Ready for Stable Release

1. **Go to private repo releases:** https://github.com/ziv-daniel/israel-bus-integration/releases
2. **Find latest pre-release** (will have beta version like `v2.0.3-beta.5`)
3. **Edit the release:**
   - **Uncheck** "Set as a pre-release" ✅
   - (Optional) Add `[minor]` or `[major]` to title if needed
   - Click **"Update release"**
4. **release-to-public.yml triggers automatically:**
   - ✅ Validates all CI passed
   - ✅ Removes `-beta` suffix
   - ✅ Syncs to public repo
   - ✅ Creates stable release
   - ✅ Uploads GTFS data
5. **HACS users can update!** 🎉

## 📊 Version Numbering Strategy

### Beta Versions (Private Repo)
- Format: `X.Y.Z-beta.N`
- Example: `2.0.3-beta.1`, `2.0.3-beta.2`, etc.
- Auto-incremented on every commit
- Only visible in private repo
- Marked as "pre-release"

### Stable Versions (Public Repo)
- Format: `X.Y.Z`
- Example: `2.0.3`, `2.1.0`, `3.0.0`
- Created when you publish a pre-release as stable
- Visible to HACS users
- Clean, meaningful version numbers

### Bump Types
- **Patch (default):** `2.0.2` → `2.0.3` (bug fixes)
- **Minor:** Add `[minor]` to release title → `2.0.2` → `2.1.0` (new features)
- **Major:** Add `[major]` to release title → `2.0.2` → `3.0.0` (breaking changes)

## 🧪 Testing the Workflow

### Test Beta Versioning (Safe)

1. Make a small commit to `main`
2. Watch auto-beta-version.yml run
3. Verify pre-release created with beta version
4. Check manifest.json updated

### Test Public Release (Do this first with a test release!)

1. Find a beta pre-release
2. Edit and uncheck "pre-release"
3. Watch release-to-public.yml run
4. Verify files synced to public repo:
   - ✅ `.claude/` NOT present
   - ✅ `tests/` NOT present
   - ✅ `custom_components/israel_transportation/` present
5. Check public repo release created

## 🔍 What Gets Synced to Public Repo

### ✅ Included
- `custom_components/israel_transportation/` (the integration)
- `README.md`, `LICENSE`, `hacs.json`
- `CHANGELOG.md`
- Essential GitHub workflows

### ❌ Excluded (via .publicignore)
- `.claude/` (skills, settings, MCP configs)
- `tests/`, `scripts/`
- `pytest.ini`, `requirements_test.txt`
- `.pre-commit-config.yaml`
- Development files and notes

## 🎯 Success Criteria

Once setup is complete, you should have:

- ✅ Beta versions auto-increment in private repo for testing
- ✅ Stable releases trigger automatic sync to public repo
- ✅ `.claude/` and other private files never appear in public repo
- ✅ HACS users only see stable versions
- ✅ Version numbers are clean and meaningful
- ✅ All CI validations must pass before public release
- ✅ GTFS data assets uploaded to public releases

## 🆘 Troubleshooting

### "Authentication failed" when syncing to public repo
- Verify `PUBLIC_REPO_TOKEN` secret is set correctly
- Check PAT token has `repo` scope
- Ensure token hasn't expired

### Beta version not incrementing
- Check auto-beta-version.yml workflow ran successfully
- Verify you have permissions to push to `main`
- Check workflow logs for errors

### Public release not triggering
- Ensure you **unchecked** "Set as a pre-release"
- Verify tag doesn't contain `-beta`, `-alpha`, or `-rc`
- Check workflow logs for validation errors

### Files not syncing correctly
- Review `.publicignore` patterns
- Check rsync command in workflow logs
- Verify files exist in private repo

## 📚 Additional Resources

- **Private Repo:** https://github.com/ziv-daniel/israel-bus-integration
- **Public Repo:** https://github.com/ziv-daniel/hass-israel-transportation-integration
- **Workflow Runs:** https://github.com/ziv-daniel/israel-bus-integration/actions
- **Release Plan:** `.claude/plans/squishy-spinning-teacup.md`

---

🎉 **You're all set!** The workflow is ready to use once you complete the manual setup steps above.
