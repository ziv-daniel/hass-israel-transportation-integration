# Israel Transportation Integration - CI Fix

Diagnose and fix CI/GitHub Actions failures for the Israel Transportation (Silent Bus) integration.

## Usage

- `/hass-fix-ci` - Diagnose current CI failures and suggest fixes
- `/hass-fix-ci --auto` - Auto-fix common issues and commit
- `/hass-fix-ci --workflow tests` - Focus on specific workflow

## Quick Diagnosis

```bash
# Check latest CI runs
gh run list --limit 10

# Find failing runs
gh run list --status failure --limit 5

# Get failure details
gh run view <run_id> --log-failed
```

## Common CI Failures & Fixes

### 1. Pre-commit Workflow Failures

**Symptoms:**
- `ruff` or `ruff-format` marked as "Failed"
- "files were modified by this hook"

**Diagnosis:**
```bash
gh run view <run_id> --log-failed | grep -A 5 "Failed"
```

**Fix:**
```bash
# Run pre-commit locally (it auto-fixes)
pre-commit run --all-files

# Stage and commit fixes
git add -A
git commit -m "Apply pre-commit formatting fixes"
git push
```

### 2. Test Workflow Failures

**Symptoms:**
- `pytest` failures
- `FAILED` test assertions

**Diagnosis:**
```bash
# Get test failure details
gh run view <run_id> --log-failed | grep -B 2 -A 10 "FAILED\|Error"
```

**Common Test Fixes:**

| Issue | Symptom | Fix |
|-------|---------|-----|
| AsyncMock issues | `'coroutine' object does not support...` | Use proper context manager pattern |
| Config flow changes | `Schema validation failed` | Update test to navigate new steps |
| API behavior change | `DID NOT RAISE` | Update test expectation |
| Import errors | `ModuleNotFoundError` | Check dependencies in `requirements_test.txt` |

**Fix workflow:**
```bash
# Run tests locally
pytest -v

# Fix failures
# ... edit test files ...

# Verify fix
pytest -v

# Commit
git add tests/
git commit -m "Fix failing tests"
git push
```

### 3. hassfest Workflow Failures

**Symptoms:**
- `manifest.json` validation errors
- Missing required files

**Diagnosis:**
```bash
gh run view <run_id> --log | grep -i "error\|warning"
```

**Common Fixes:**
- Add missing fields to `manifest.json`
- Fix invalid `iot_class` value
- Correct `documentation` or `issue_tracker` URLs

### 4. HACS Workflow Failures

**Symptoms:**
- `hacs.json` validation errors
- Missing `hacs.json` file

**Diagnosis:**
```bash
gh run view <run_id> --log | grep -i "hacs"
```

**Common Fixes:**
- Ensure `hacs.json` has required fields: `name`, `homeassistant`
- Remove deprecated fields like `domains`

## Automated Fix Workflow

### Step 1: Identify Failures
```bash
# List all failing workflows
FAILED_RUNS=$(gh run list --status failure --json databaseId,name --limit 5)
echo $FAILED_RUNS
```

### Step 2: Get Details
```bash
# For each failed run
for run_id in $(echo $FAILED_RUNS | jq -r '.[].databaseId'); do
    echo "=== Run $run_id ==="
    gh run view $run_id --log-failed | head -50
done
```

### Step 3: Apply Fixes
```bash
# Pre-commit fixes (auto-applied)
pre-commit run --all-files

# If tests fail, run locally to debug
pytest -v --tb=long

# Check for import issues
python -c "from custom_components.silent_bus import api, config_flow, coordinator, sensor"
```

### Step 4: Verify & Push
```bash
# Full verification
pre-commit run --all-files && pytest -v

# Commit and push
git add -A
git commit -m "Fix CI failures"
git push

# Monitor new run
gh run watch
```

## CI Workflow Reference

| Workflow | Trigger | What it checks |
|----------|---------|----------------|
| `tests.yaml` | Push, PR | pytest, coverage |
| `pre-commit.yaml` | Push, PR | ruff, formatting |
| `hassfest.yaml` | Push, PR, daily | HA manifest validation |
| `hacs.yaml` | Push, PR | HACS requirements |
| `release-drafter.yaml` | Push to main | Auto-generate release notes |
| `publish.yaml` | Version tag | Create GitHub release |

## Re-running Failed Workflows

```bash
# Re-run a specific workflow
gh run rerun <run_id>

# Re-run failed jobs only
gh run rerun <run_id> --failed

# Trigger workflow manually
gh workflow run tests.yaml
```

## Debugging Tips

### Compare Local vs CI
```bash
# Check Python version
python --version

# CI uses matrix of versions
# Python 3.12, 3.13
# HA versions: 2024.12, 2025.x

# Test with specific Python
python3.12 -m pytest -v
```

### Check Dependencies
```bash
# Local deps
pip freeze | grep -E "pytest|homeassistant|aiohttp"

# Compare with requirements_test.txt
cat requirements_test.txt
```

### Environment Differences
```bash
# CI runs on Ubuntu, you may be on Windows
# Path separators differ: / vs \
# Line endings differ: LF vs CRLF

# Ensure .gitattributes handles this
cat .gitattributes
```

## Quick Fix Commands

```bash
# Fix all pre-commit issues
pre-commit run --all-files

# Fix ruff specifically
ruff check --fix .
ruff format .

# Fix end-of-file issues
# Add newline to files missing it
echo "" >> path/to/file.json

# Run failed workflow again
gh run rerun $(gh run list --status failure -L 1 --json databaseId -q '.[0].databaseId')
```

## Related Files

- `.github/workflows/` - All workflow definitions
- `.pre-commit-config.yaml` - Pre-commit hooks
- `pyproject.toml` - Ruff configuration
- `pytest.ini` - Pytest configuration
- `requirements_test.txt` - Test dependencies
