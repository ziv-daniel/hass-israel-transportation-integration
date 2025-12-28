# Israel Transportation Integration - Validation

Validate the Israel Transportation (Silent Bus) integration against Home Assistant and HACS standards with intelligent issue detection and auto-fix capabilities.

## Usage

- `/hass-validate-integration` - Run all validation checks
- `/hass-validate-integration --strict` - Run with stricter checks for release
- `/hass-validate-integration --fix` - Auto-fix common issues

## Smart Validation Workflow

### Phase 1: Manifest Validation

Check `custom_components/silent_bus/manifest.json`:

```bash
python -c "
import json
with open('custom_components/silent_bus/manifest.json') as f:
    m = json.load(f)
    required = ['domain', 'name', 'version', 'documentation', 'issue_tracker', 'iot_class', 'requirements', 'codeowners']
    missing = [k for k in required if k not in m]
    if missing:
        print(f'Missing required fields: {missing}')
    else:
        print(f'Manifest OK - version {m[\"version\"]}')
"
```

**Expected Fields:**
| Field | Current Value | Validation |
|-------|--------------|------------|
| domain | `silent_bus` | Must match folder name |
| name | `Israel Transportation` | User-facing name |
| version | `1.3.3` | Semver format |
| documentation | GitHub URL | Must be valid URL |
| issue_tracker | GitHub issues URL | Must be valid URL |
| iot_class | `cloud_polling` | Valid HA IoT class |
| requirements | `["aiohttp>=3.9.0"]` | External dependencies |
| codeowners | `["@ziv-daniel"]` | GitHub usernames |

### Phase 2: HACS Validation

Check `hacs.json`:

```bash
python -c "
import json
with open('hacs.json') as f:
    h = json.load(f)
    required = ['name', 'homeassistant']
    missing = [k for k in required if k not in h]
    if missing:
        print(f'Missing: {missing}')
    else:
        print(f'HACS OK - min HA version: {h[\"homeassistant\"]}')
"
```

### Phase 3: Translation Validation

Check translation completeness:

```bash
python -c "
import json
import os

strings = json.load(open('custom_components/silent_bus/strings.json'))
en = json.load(open('custom_components/silent_bus/translations/en.json'))
he = json.load(open('custom_components/silent_bus/translations/he.json'))

def get_keys(d, prefix=''):
    keys = set()
    for k, v in d.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            keys.update(get_keys(v, key))
        else:
            keys.add(key)
    return keys

en_keys = get_keys(en)
he_keys = get_keys(he)

missing_in_he = en_keys - he_keys
missing_in_en = he_keys - en_keys

if missing_in_he:
    print(f'Missing in Hebrew: {missing_in_he}')
if missing_in_en:
    print(f'Missing in English: {missing_in_en}')
if not missing_in_he and not missing_in_en:
    print('Translations OK - all keys match')
"
```

### Phase 4: Version Consistency

```bash
python -c "
import json
import re

# Get manifest version
manifest = json.load(open('custom_components/silent_bus/manifest.json'))
version = manifest['version']

# Check CHANGELOG
with open('CHANGELOG.md') as f:
    changelog = f.read()
    if f'## [{version}]' in changelog or f'## [v{version}]' in changelog:
        print(f'CHANGELOG OK - version {version} documented')
    else:
        print(f'WARNING: Version {version} not in CHANGELOG.md')
"
```

### Phase 5: File Structure Validation

```bash
# Required files
ls -la custom_components/silent_bus/__init__.py
ls -la custom_components/silent_bus/manifest.json
ls -la custom_components/silent_bus/config_flow.py
ls -la custom_components/silent_bus/const.py
ls -la custom_components/silent_bus/sensor.py
ls -la custom_components/silent_bus/strings.json
ls -la custom_components/silent_bus/translations/en.json
ls -la custom_components/silent_bus/translations/he.json
ls -la hacs.json
ls -la CHANGELOG.md
```

## Common Issues & Auto-Fixes

### Issue 1: Version Mismatch
**Symptom:** Manifest version doesn't match CHANGELOG

**Auto-fix:**
```python
# Update CHANGELOG with new version entry
import datetime
today = datetime.date.today().isoformat()
version = "1.3.3"
entry = f"\n## [{version}] - {today}\n\n### Changed\n- Updated version\n"
# Add to CHANGELOG.md after first line
```

### Issue 2: Missing Translation Keys
**Symptom:** Hebrew translation missing keys

**Auto-fix:** Copy English key with `TODO: Translate` marker

### Issue 3: Invalid IoT Class
**Symptom:** `iot_class` not in allowed values

**Valid values:** `cloud_polling`, `cloud_push`, `local_polling`, `local_push`, `calculated`, `assumed_state`

### Issue 4: HACS deprecated fields
**Symptom:** Warning about deprecated fields like `domains`

**Auto-fix:** Remove deprecated fields from `hacs.json`

## GitHub Actions Validation

These validations run automatically in CI:

```bash
# Check hassfest workflow status
gh run list --workflow=hassfest.yaml --limit 3

# Check HACS workflow status
gh run list --workflow=hacs.yaml --limit 3

# Trigger manual validation
gh workflow run hassfest.yaml
gh workflow run hacs.yaml
```

## Pre-Release Checklist

Before tagging a release, verify:

- [ ] **Version updated:** `manifest.json` has new version
- [ ] **CHANGELOG updated:** Entry for new version with date
- [ ] **Translations complete:** All keys in en.json and he.json
- [ ] **Tests passing:** `/hass-test-integration`
- [ ] **Pre-commit clean:** `pre-commit run --all-files`
- [ ] **hassfest passing:** Check GitHub Actions
- [ ] **HACS passing:** Check GitHub Actions
- [ ] **Git clean:** No uncommitted changes

## Quick Validation Command

Run all validations in one go:

```bash
# Full validation suite
pre-commit run --all-files && \
python -c "import json; m=json.load(open('custom_components/silent_bus/manifest.json')); print(f'Version: {m[\"version\"]}')" && \
pytest -v --tb=short
```

## Related Files

- `custom_components/silent_bus/manifest.json` - Integration metadata
- `custom_components/silent_bus/strings.json` - UI strings source
- `custom_components/silent_bus/translations/` - Language files
- `hacs.json` - HACS configuration
- `CHANGELOG.md` - Version history
- `.github/workflows/hassfest.yaml` - HA validation workflow
- `.github/workflows/hacs.yaml` - HACS validation workflow

## Documentation Links

- [Home Assistant Integration Manifest](https://developers.home-assistant.io/docs/creating_integration_manifest)
- [HACS Requirements](https://hacs.xyz/docs/publish/start)
- [Home Assistant Translations](https://developers.home-assistant.io/docs/internationalization)
