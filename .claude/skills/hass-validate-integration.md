# Home Assistant Integration Validation

Validate the Silent Bus integration against Home Assistant and HACS standards.

## Usage

- `/hass-validate-integration` - Run all validation checks
- `/hass-validate-integration --strict` - Run with stricter checks for release
- `/hass-validate-integration --hassfest-only` - Only run hassfest validation
- `/hass-validate-integration --hacs-only` - Only run HACS validation

## What it does

1. Validates `manifest.json` structure and required fields
2. Checks `strings.json` and translations completeness
3. Verifies HACS requirements in `hacs.json`
4. Validates version consistency across files
5. Checks for required integration files
6. Validates service definitions in `services.yaml`
7. Runs hassfest validation (if available locally)

## Commands executed

```bash
# Step 1: Check manifest.json validity
python -c "import json; json.load(open('custom_components/silent_bus/manifest.json'))"

# Step 2: Verify required files exist
ls custom_components/silent_bus/__init__.py
ls custom_components/silent_bus/manifest.json
ls custom_components/silent_bus/strings.json
ls custom_components/silent_bus/translations/en.json

# Step 3: Check version consistency
VERSION=$(python -c "import json; print(json.load(open('custom_components/silent_bus/manifest.json'))['version'])")
echo "Manifest version: $VERSION"
grep -q "## \[$VERSION\]" CHANGELOG.md && echo "CHANGELOG matches" || echo "WARNING: Version mismatch in CHANGELOG"

# Step 4: Validate HACS configuration
python -c "import json; data=json.load(open('hacs.json')); assert 'name' in data; assert 'homeassistant' in data"

# Step 5: Check translation completeness
python -c "
import json
en = json.load(open('custom_components/silent_bus/translations/en.json'))
he = json.load(open('custom_components/silent_bus/translations/he.json'))
assert en.keys() == he.keys(), 'Translation keys mismatch'
print('Translation files are consistent')
"
```

## Validation checklist

### manifest.json Requirements
- [x] `domain` field present and matches directory name
- [x] `name` field present
- [x] `version` field present and follows semver
- [x] `documentation` URL is valid
- [x] `issue_tracker` URL is valid
- [x] `iot_class` is set correctly (`cloud_polling`)
- [x] `requirements` lists all external dependencies
- [x] `codeowners` includes GitHub username

### HACS Requirements (hacs.json)
- [x] `name` field matches integration name
- [x] `homeassistant` minimum version specified
- [x] `render_readme` set to true

### Translation Requirements
- [x] `strings.json` exists with all config flow steps
- [x] `translations/en.json` exists and complete
- [x] `translations/he.json` exists and matches English keys
- [x] All config flow steps have translations

### File Structure Requirements
- [x] `__init__.py` with async_setup_entry
- [x] `config_flow.py` with ConfigFlow class
- [x] `const.py` with DOMAIN constant
- [x] `manifest.json` with all required fields
- [x] `strings.json` for UI strings
- [x] `services.yaml` for service definitions

## Common issues

**Issue**: `manifest.json` validation fails
**Solution**: Ensure all required fields are present: domain, name, version, documentation, issue_tracker, iot_class, requirements

**Issue**: Translation mismatch between en.json and he.json
**Solution**: Ensure both translation files have the same keys. Run:
```bash
python -c "import json; en=set(json.load(open('custom_components/silent_bus/translations/en.json')).keys()); he=set(json.load(open('custom_components/silent_bus/translations/he.json')).keys()); print('Missing in he:', en-he); print('Missing in en:', he-en)"
```

**Issue**: Version mismatch between manifest.json and CHANGELOG.md
**Solution**: Update the version in manifest.json to match the latest version in CHANGELOG.md, or vice versa

**Issue**: HACS validation fails
**Solution**: Ensure `hacs.json` has `name` and `homeassistant` fields. Remove invalid fields like `domains` (removed in recent commits)

**Issue**: hassfest not available locally
**Solution**: hassfest runs in GitHub Actions. Push to GitHub and check the hassfest workflow results

## GitHub Actions integration

This integration uses GitHub Actions for automated validation:

- **hassfest.yaml**: Validates integration structure daily and on push/PR
- **hacs.yaml**: Validates HACS requirements

To manually trigger validation:
```bash
gh workflow run hassfest.yaml
gh workflow run hacs.yaml
```

## Pre-release validation

Before creating a release, ensure:

1. Version updated in `manifest.json`
2. Matching version entry in `CHANGELOG.md`
3. All tests passing (`/hass-test-integration`)
4. hassfest validation passing
5. HACS validation passing
6. No linting errors (`pre-commit run --all-files`)

## Related files

- `custom_components/silent_bus/manifest.json` - Integration metadata
- `custom_components/silent_bus/strings.json` - UI strings
- `custom_components/silent_bus/translations/` - Multi-language support
- `hacs.json` - HACS configuration
- `CHANGELOG.md` - Version history
- `.github/workflows/hassfest.yaml` - hassfest validation workflow
- `.github/workflows/hacs.yaml` - HACS validation workflow

## Documentation links

- [Home Assistant Integration Manifest](https://developers.home-assistant.io/docs/creating_integration_manifest)
- [HACS Requirements](https://hacs.xyz/docs/publish/start)
- [Home Assistant Translations](https://developers.home-assistant.io/docs/internationalization)
