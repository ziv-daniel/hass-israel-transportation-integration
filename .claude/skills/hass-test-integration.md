# Home Assistant Integration Testing

Run comprehensive test suite for the Silent Bus integration with coverage reporting.

## Usage

- `/hass-test-integration` - Run full test suite with coverage
- `/hass-test-integration --quick` - Run tests without coverage report
- `/hass-test-integration --html` - Generate HTML coverage report

## What it does

1. Runs pre-commit checks (Ruff linting and formatting)
2. Executes pytest for all unit and integration tests
3. Generates coverage report
4. Identifies untested code paths
5. Optionally creates HTML coverage report for detailed analysis

## Commands executed

```bash
# Step 1: Run pre-commit checks
pre-commit run --all-files

# Step 2: Run pytest with coverage
pytest --cov=custom_components.silent_bus --cov-report=term-missing

# Step 3 (optional): Generate HTML coverage report
pytest --cov=custom_components.silent_bus --cov-report=html
```

## Test coverage targets

- **API Client** (`api.py`): Connection handling, retry logic, error handling
- **Config Flow** (`config_flow.py`): Multi-step configuration, validation
- **Coordinator** (`coordinator.py`): Data updates, dynamic polling intervals
- **Sensors** (`sensor.py`): Entity state, attributes, device class

## Common issues

**Issue**: `ModuleNotFoundError: No module named 'pytest'`
**Solution**: Install test dependencies: `pip install -r requirements_test.txt`

**Issue**: Tests fail with import errors
**Solution**: Ensure you're running from the repository root directory

**Issue**: Pre-commit hooks not found
**Solution**: Install pre-commit: `pip install pre-commit && pre-commit install`

**Issue**: Coverage report shows low coverage
**Solution**: Review uncovered lines in the terminal output (marked with `!!!!`) and add tests for those code paths

## Expected output

```
============================= test session starts ==============================
collected 45 items

tests/unit/test_api.py ................                                   [ 35%]
tests/unit/test_config_flow.py .........                                  [ 55%]
tests/unit/test_coordinator.py ......                                     [ 68%]
tests/unit/test_sensor.py ..............                                  [100%]

---------- coverage: platform win32, python 3.13.1-final-0 -----------
Name                                          Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------
custom_components\silent_bus\__init__.py         95      2    98%   45, 89
custom_components\silent_bus\api.py             120      5    96%   78-82
custom_components\silent_bus\config_flow.py     145      8    94%   102, 156-162
custom_components\silent_bus\coordinator.py     180     10    94%   145-154
custom_components\silent_bus\sensor.py          200     12    94%   89, 167-177
---------------------------------------------------------------------------
TOTAL                                           740     37    95%

============================== 45 passed in 2.34s ===============================
```

## Integration with Home Assistant

This skill uses the Home Assistant test infrastructure:
- `pytest-homeassistant-custom-component` for HA-specific test utilities
- Mock `hass` fixtures for Home Assistant core
- Async test support via `pytest-asyncio`

## Related files

- `tests/conftest.py` - Test fixtures and mock setup
- `tests/unit/` - Unit tests for each component
- `tests/integration/` - Full integration tests
- `pytest.ini` - Pytest configuration
- `.pre-commit-config.yaml` - Pre-commit hook configuration
