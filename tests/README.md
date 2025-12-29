# Silent Bus Integration Tests

This directory contains comprehensive tests for the Silent Bus Home Assistant integration.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                          # Shared fixtures and test configuration
├── README.md                            # This file
├── unit/                                # Unit tests (isolated, mocked)
│   ├── test_api.py                     # API client unit tests
│   ├── test_config_flow.py             # Config flow unit tests
│   └── test_sensor.py                  # Sensor entity unit tests
└── integration/                         # Integration tests (end-to-end)
    ├── test_init.py                    # Integration setup tests
    ├── test_config_flow_integration.py # Config flow integration tests
    └── test_api_integration.py         # API endpoint integration tests
```

## Running Tests

### Run All Tests

```bash
# From the repository root
pytest tests/

# With verbose output
pytest -v tests/

# With coverage report
pytest --cov=custom_components.israel_transportation --cov-report=html tests/
```

### Run Only Unit Tests

```bash
pytest tests/unit/
```

### Run Only Integration Tests

```bash
pytest tests/integration/
```

### Run Specific Test File

```bash
pytest tests/integration/test_config_flow_integration.py
```

### Run Specific Test Function

```bash
pytest tests/integration/test_config_flow_integration.py::test_bus_station_12664_validation
```

### Run Tests with Coverage

```bash
# Generate coverage report
pytest --cov=custom_components.israel_transportation --cov-report=term-missing tests/

# Generate HTML coverage report
pytest --cov=custom_components.israel_transportation --cov-report=html tests/
# Then open htmlcov/index.html in your browser
```

### Run Tests Matching Pattern

```bash
# Run all tests with "bus" in the name
pytest -k "bus" tests/

# Run all tests for station 12664
pytest -k "12664" tests/
```

## Test Categories

### Unit Tests (`tests/unit/`)

Unit tests focus on testing individual components in isolation with mocked dependencies:

- **`test_api.py`**: Tests the BusNearbyApiClient class
  - Session management
  - Request formatting
  - Response parsing
  - Error handling
  - Retry logic

- **`test_config_flow.py`**: Tests the configuration flow logic
  - Form validation
  - User input handling
  - Error messages
  - Options flow

- **`test_sensor.py`**: Tests sensor entities
  - State updates
  - Attribute management
  - Data formatting

### Integration Tests (`tests/integration/`)

Integration tests verify end-to-end functionality with realistic scenarios:

- **`test_init.py`**: Tests integration setup and lifecycle
  - Component initialization
  - Platform loading
  - Coordinator setup

- **`test_config_flow_integration.py`**: Comprehensive config flow tests covering all transport types
  - **Bus Station Tests**: Validates bus station configuration including the critical station 12664 test case
  - **Train Station Tests**: Tests train route configuration with origin/destination
  - **Light Rail Tests**: Validates light rail station and line configuration
  - **Common Flow Tests**: Tests shared functionality like duplicate prevention and options flow

- **`test_api_integration.py`**: Tests API endpoint integration
  - Search station endpoint
  - Station 12664 specific validation (regression test)
  - Get stop times endpoint
  - Error handling and retries

## Critical Test Cases

### Station 12664 Test Case

The **station 12664** test case is particularly important as it validates the fix for a user-reported issue where this specific station was not being validated correctly.

**Related test functions:**
- `tests/integration/test_config_flow_integration.py::test_bus_station_12664_validation`
- `tests/integration/test_api_integration.py::test_search_station_12664_specific`
- `tests/integration/test_api_integration.py::test_validate_station_12664_specific`

Run these specific tests:
```bash
pytest -k "12664" tests/
```

## Test Coverage Goals

The project maintains **>90% test coverage** for all core components:

- API client (`api.py`): >95% coverage
- Config flow (`config_flow.py`): >90% coverage
- Sensor (`sensor.py`): >90% coverage
- Coordinator (`coordinator.py`): >85% coverage

Check current coverage:
```bash
pytest --cov=custom_components.israel_transportation --cov-report=term-missing tests/
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_<component>.py`
- Test functions: `test_<what_is_being_tested>`
- Use descriptive names that explain what is being tested

### Example Test Structure

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_specific_functionality(hass):
    """Test description explaining what this test validates.

    Include context about why this test is important.
    """
    # Arrange: Set up test data and mocks
    with patch("custom_components.israel_transportation.api.BusNearbyApiClient") as mock_client:
        mock_client.return_value.search_station = AsyncMock(
            return_value=[{"stop_id": "12345", "name": "Test Station"}]
        )

        # Act: Execute the code being tested
        result = await some_function()

        # Assert: Verify the results
        assert result is not None
        assert result["stop_id"] == "12345"
```

### Using Fixtures

Common fixtures are defined in `conftest.py`:

- `hass`: Home Assistant instance
- `mock_api_client`: Mocked API client with default responses
- `mock_config_entry`: Sample config entry
- `setup_integration`: Fully configured integration

Example usage:
```python
@pytest.mark.asyncio
async def test_with_fixture(hass, mock_api_client):
    """Test using fixtures."""
    # Use the fixtures in your test
    result = await mock_api_client.search_station("12345")
    assert len(result) > 0
```

## Common Testing Patterns

### Mocking API Responses

```python
from unittest.mock import AsyncMock, MagicMock

mock_response = MagicMock()
mock_response.json = AsyncMock(return_value={"data": "value"})
mock_response.raise_for_status = MagicMock()

mock_session = MagicMock(spec=aiohttp.ClientSession)
mock_session.get = MagicMock(
    return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
)
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_error_handling(hass):
    """Test that errors are handled gracefully."""
    with patch("custom_components.israel_transportation.api.BusNearbyApiClient") as mock:
        mock.return_value.search_station = AsyncMock(
            side_effect=ApiConnectionError("Connection failed")
        )

        # Verify error is handled appropriately
        result = await function_under_test()
        assert result["errors"] == {"base": "cannot_connect"}
```

### Testing Config Flow

```python
@pytest.mark.asyncio
async def test_config_flow_step(hass):
    """Test a config flow step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Configure the flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"station_id": "12345"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
```

## Continuous Integration

Tests are automatically run on every commit via GitHub Actions. The CI pipeline:

1. Runs all tests across multiple Home Assistant versions
2. Generates coverage reports
3. Fails if coverage drops below 90%
4. Validates code style and formatting

## Troubleshooting

### Tests Fail Locally But Pass in CI

- Ensure you have the latest dependencies: `pip install -r requirements_test.txt`
- Clear pytest cache: `pytest --cache-clear`
- Check Home Assistant version: `pip show homeassistant`

### Import Errors

- Make sure you're running pytest from the repository root
- Verify virtual environment is activated
- Install test dependencies: `pip install -r requirements_test.txt`

### Async Test Warnings

All async tests must be marked with `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function(hass):
    """Test async functionality."""
    result = await async_function()
    assert result is not None
```

### Mock Not Working as Expected

- Ensure the patch path matches the import path in the code under test
- Use `AsyncMock` for async functions, `MagicMock` for sync functions
- Check that `return_value` vs `side_effect` is used appropriately

## Additional Resources

- [Home Assistant Testing Documentation](https://developers.home-assistant.io/docs/development_testing/)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component)

## Questions or Issues?

If you encounter issues with tests or need help writing new tests, please:

1. Check this README for guidance
2. Look at existing tests for examples
3. Review the test output for specific error messages
4. Open an issue on GitHub with details about the problem
