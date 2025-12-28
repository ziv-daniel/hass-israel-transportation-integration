# Israel Transportation Integration - Test Suite

Run comprehensive test suite for the Israel Transportation (Silent Bus) integration with intelligent analysis and auto-fix suggestions.

## Usage

- `/hass-test-integration` - Run full test suite with coverage and analysis
- `/hass-test-integration --quick` - Run tests without coverage report
- `/hass-test-integration --fix` - Run tests and auto-fix common issues found

## Smart Workflow

### Step 1: Pre-flight Checks
Before running tests, verify the environment is ready:

```bash
# Check Python environment
python --version

# Verify test dependencies are installed
pip show pytest pytest-asyncio pytest-homeassistant-custom-component pytest-cov aiohttp

# If missing, install:
pip install -r requirements_test.txt
```

### Step 2: Run Pre-commit Checks
Always run pre-commit before tests to catch formatting issues:

```bash
pre-commit run --all-files
```

**Auto-fix strategy:** If pre-commit modifies files, commit those changes before proceeding.

### Step 3: Run Test Suite
```bash
# Full test with coverage
pytest --cov=custom_components.silent_bus --cov-report=term-missing -v

# Quick run without coverage
pytest -v

# Run specific test file
pytest tests/unit/test_api.py -v

# Run specific test
pytest tests/unit/test_api.py::test_search_station -v
```

## Test Coverage Map

| Component | File | Key Test Areas |
|-----------|------|----------------|
| API Client | `tests/unit/test_api.py` | Connection handling, retry logic, response parsing |
| API Integration | `tests/integration/test_api_integration.py` | End-to-end API calls, error scenarios |
| Config Flow | `tests/unit/test_config_flow.py` | Step navigation, validation, entry creation |
| Config Flow Integration | `tests/integration/test_config_flow_integration.py` | Full flow with mocked API |
| Coordinator | `tests/unit/test_coordinator.py` | Data updates, dynamic polling |
| Sensors | `tests/unit/test_sensor.py` | Entity state, attributes |

## Common Failure Patterns & Solutions

### Pattern 1: AsyncMock Context Manager Issues
**Symptom:** `'coroutine' object does not support the asynchronous context manager protocol`

**Root Cause:** Calling `AsyncMock()()` (with trailing `()`) returns a coroutine, not a context manager.

**Fix:**
```python
# WRONG
return AsyncMock(__aenter__=AsyncMock(return_value=mock_response))()

# CORRECT
cm = AsyncMock()
cm.__aenter__ = AsyncMock(return_value=mock_response)
cm.__aexit__ = AsyncMock(return_value=None)
return cm
```

### Pattern 2: Config Flow Step Navigation
**Symptom:** `Schema validation failed @ data['field_name']`

**Root Cause:** Config flow has intermediate steps (e.g., `station_selection_method`) that tests skip.

**Fix:** Navigate through all steps:
```python
# Navigate through all steps
result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TRANSPORT_TYPE: TRANSPORT_TYPE_BUS})
result = await hass.config_entries.flow.async_configure(result["flow_id"], {"selection_method": "manual"})
result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_STATION_ID: "24068"})
```

### Pattern 3: API Behavior Changes
**Symptom:** Test expects exception but code returns empty list

**Root Cause:** API was updated to handle gracefully (e.g., missing 'times' key returns `[]`)

**Fix:** Update test expectations to match new behavior.

### Pattern 4: Unused Import Warnings
**Symptom:** `F401 imported but unused`

**Fix:** Remove unused imports or add to `__all__` if intentionally exported.

## Intelligent Analysis

When tests fail, analyze:

1. **Check recent changes:** `git diff HEAD~5 -- tests/`
2. **Compare with implementation:** Is the test outdated vs. current code?
3. **Look for patterns:** Multiple similar failures suggest systemic issue
4. **Check GitHub Actions:** Compare local vs CI results

## Integration with CI

Tests run automatically in GitHub Actions:
- **Trigger:** Push to main, PRs
- **Matrix:** Python 3.12/3.13, HA 2024.12/2025.x
- **Artifacts:** Coverage reports

Check CI status:
```bash
gh run list --workflow=tests.yaml --limit 5
gh run view <run_id> --log-failed
```

## Developer Checklist

Before committing test changes:

- [ ] All tests pass locally: `pytest -v`
- [ ] Pre-commit passes: `pre-commit run --all-files`
- [ ] Coverage maintained: Check `--cov-report=term-missing`
- [ ] No flaky tests: Run 3x to verify consistency
- [ ] Test isolation: Each test is independent

## Related Files

- `tests/conftest.py` - Shared fixtures
- `pytest.ini` - Pytest configuration
- `.pre-commit-config.yaml` - Pre-commit hooks
- `requirements_test.txt` - Test dependencies
- `.github/workflows/tests.yaml` - CI workflow
