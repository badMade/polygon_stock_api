# Testing Guide

This guide covers the test strategy, organization, and execution for the Stock Data Retrieval System.

## Table of Contents

- [Test Overview](#test-overview)
- [Test Organization](#test-organization)
- [Running Tests](#running-tests)
- [Test Markers](#test-markers)
- [Writing Tests](#writing-tests)
- [Test Fixtures](#test-fixtures)
- [Coverage](#coverage)
- [CI/CD Integration](#cicd-integration)

---

## Test Overview

### Test Statistics

| Metric | Value |
|--------|-------|
| Total Test Files | 17 |
| Total Tests | 375+ |
| Coverage Target | 85% |
| Test Framework | pytest |

### Test Philosophy

1. **Unit Tests First** - Test individual functions in isolation
2. **Integration Tests** - Test component interactions
3. **Real API Tests** - Optional tests against live APIs (skipped by default)
4. **Performance Tests** - Baseline benchmarks for speed and memory

---

## Test Organization

### Test File Structure

```
tests/
├── conftest.py                      # Shared fixtures and helpers
├── test_execute_stock_retrieval.py  # StockDataExecutor tests
├── test_production_stock_retrieval.py # ProductionStockRetriever tests
├── test_stock_notion_retrieval.py   # StockDataNotionRetriever tests
├── test_execute_complete_production.py # Pipeline runner tests
├── test_upload_to_notion.py         # Upload handler tests
├── test_integration.py              # End-to-end workflow tests
├── test_error_recovery.py           # Checkpoint and recovery tests
├── test_api_response_handling.py    # API response parsing tests
├── test_data_validation.py          # Data quality validation tests
├── test_filesystem_edge_cases.py    # File I/O edge case tests
├── test_logging_verification.py     # Logging output tests
├── test_configuration.py            # Configuration and env var tests
├── test_real_api_integration.py     # Real Polygon API tests
├── test_performance_speed.py        # Processing speed tests
├── test_performance_memory.py       # Memory usage tests
├── test_performance_rate_limiting.py # Rate limiting tests
└── test_performance_scalability.py  # Scalability tests
```

### Test Categories

| Category | Files | Purpose |
|----------|-------|---------|
| **Unit Tests** | `test_*_retrieval.py`, `test_upload_*.py` | Test individual classes/methods |
| **Integration** | `test_integration.py` | Test complete workflows |
| **Error Handling** | `test_error_recovery.py`, `test_filesystem_*.py` | Test failure scenarios |
| **Validation** | `test_data_validation.py`, `test_api_response_*.py` | Test data quality |
| **Performance** | `test_performance_*.py` | Test speed/memory/scaling |
| **Real API** | `test_real_api_integration.py` | Test against live APIs |
| **Configuration** | `test_configuration.py` | Test settings and env vars |

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_integration.py

# Run specific test class
pytest tests/test_integration.py::TestEndToEndWorkflow

# Run specific test
pytest tests/test_integration.py::TestEndToEndWorkflow::test_complete_ticker_to_batch_file_workflow

# Run tests matching pattern
pytest -k "checkpoint"
```

### Common Test Scenarios

```bash
# Quick validation (exclude slow tests)
pytest -m "not slow"

# Unit tests only (exclude integration)
pytest -m "not integration"

# Full test suite with coverage
pytest --cov=. --cov-report=html

# Run failed tests from last run
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

---

## Test Markers

### Available Markers

| Marker | Description | Default |
|--------|-------------|---------|
| `slow` | Long-running tests (>1s) | Included |
| `integration` | End-to-end workflow tests | Included |
| `real_api` | Tests requiring live API access | **Excluded** |

### Using Markers

```bash
# Exclude slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run real API tests (requires credentials)
pytest -m real_api

# Combine markers
pytest -m "integration and not slow"
pytest -m "not (slow or real_api)"
```

### Marking Tests in Code

```python
import pytest

@pytest.mark.slow
def test_process_large_dataset():
    """This test takes several seconds."""
    pass

@pytest.mark.integration
def test_full_pipeline():
    """This tests the complete workflow."""
    pass

@pytest.mark.real_api
def test_polygon_api_connection():
    """This requires POLYGON_API_KEY to be set."""
    pass

# Multiple markers
@pytest.mark.slow
@pytest.mark.integration
def test_complete_production_run():
    pass
```

### Real API Tests

Real API tests are **skipped by default** because they:
- Require valid API credentials
- Make actual network requests
- Count against API rate limits
- May incur costs on paid plans

**To run real API tests:**

1. Set up credentials (see [API_SETUP.md](API_SETUP.md))
2. Export environment variables:
   ```bash
   export POLYGON_API_KEY="your_key_here"
   ```
3. Run with the marker:
   ```bash
   pytest -m real_api -v
   ```

---

## Writing Tests

### Test Structure

Follow the Arrange-Act-Assert pattern:

```python
def test_load_tickers_success(self, temp_dir):
    """Test successful ticker loading from JSON file."""
    # Arrange - Set up test data
    tickers = ["AAPL", "MSFT", "GOOGL"]
    ticker_file = os.path.join(temp_dir, "tickers.json")
    with open(ticker_file, 'w') as f:
        json.dump(tickers, f)

    retriever = ProductionStockRetriever()
    retriever.ticker_file = ticker_file

    # Act - Execute the code under test
    retriever.load_tickers()

    # Assert - Verify the results
    assert len(retriever.tickers) == 3
    assert retriever.tickers == tickers
```

### Test Naming Conventions

```python
# Good: Descriptive names that explain what's being tested
def test_load_tickers_returns_empty_list_for_empty_file():
def test_process_batch_updates_counter_correctly():
def test_checkpoint_recovery_after_interruption():

# Bad: Vague names
def test_load():
def test_process():
def test_checkpoint():
```

### Testing Exceptions

```python
def test_load_tickers_file_not_found(self):
    """Test FileNotFoundError when ticker file doesn't exist."""
    retriever = ProductionStockRetriever()
    retriever.ticker_file = "/nonexistent/path/tickers.json"

    with pytest.raises(FileNotFoundError):
        retriever.load_tickers()
```

### Parametrized Tests

```python
@pytest.mark.parametrize("batch_size,expected_batches", [
    (100, 1),
    (50, 2),
    (25, 4),
])
def test_batch_calculation(self, batch_size, expected_batches):
    """Test batch count calculation with various sizes."""
    tickers = ["TICK"] * 100
    batches = (len(tickers) + batch_size - 1) // batch_size
    assert batches == expected_batches
```

### Mocking External Dependencies

```python
from unittest.mock import patch, MagicMock

def test_api_call_with_mock(self):
    """Test API handling with mocked response."""
    mock_response = {
        "results": [{"o": 150.0, "c": 155.0, "h": 156.0, "l": 149.0}],
        "status": "OK"
    }

    with patch('production_stock_retrieval.requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.status_code = 200

        result = retriever.get_polygon_data("AAPL", period)

        assert result["has_data"] is True
        mock_get.assert_called_once()
```

---

## Test Fixtures

### Built-in Fixtures (conftest.py)

```python
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files.

    Yields:
        str: Path to temporary directory (cleaned up after test)
    """

@pytest.fixture
def sample_tickers():
    """Provide a list of sample ticker symbols.

    Returns:
        list: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    """

@pytest.fixture
def sample_batch_data():
    """Provide sample batch data structure.

    Returns:
        dict: Complete batch data with pages and metadata
    """

@pytest.fixture
def realistic_polygon_response():
    """Provide realistic Polygon API response format.

    Returns:
        dict: Mock API response with results array
    """

@pytest.fixture
def checkpoint_file(temp_dir):
    """Create a valid checkpoint file.

    Returns:
        str: Path to checkpoint JSON file
    """
```

### Using Fixtures

```python
def test_with_temp_directory(self, temp_dir):
    """Test using temporary directory fixture."""
    file_path = os.path.join(temp_dir, "test.json")
    # temp_dir is automatically cleaned up after test

def test_with_sample_data(self, sample_tickers, sample_batch_data):
    """Test using multiple fixtures."""
    assert len(sample_tickers) == 5
    assert "pages" in sample_batch_data
```

### Creating Custom Fixtures

```python
@pytest.fixture
def configured_retriever(temp_dir):
    """Create a fully configured retriever for testing."""
    tickers = ["AAPL", "MSFT"]
    ticker_file = os.path.join(temp_dir, "tickers.json")
    with open(ticker_file, 'w') as f:
        json.dump(tickers, f)

    retriever = ProductionStockRetriever()
    retriever.ticker_file = ticker_file
    retriever.load_tickers()

    return retriever
```

---

## Coverage

### Coverage Configuration

From `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["."]
omit = ["tests/*", "setup.py", "conftest.py"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
fail_under = 85
show_missing = true
```

### Running Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=term-missing

# Generate HTML report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Check coverage meets threshold
pytest --cov=. --cov-fail-under=85
```

### Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| Overall | 85% | ~85% |
| Core modules | 90% | ~88% |
| Error handling | 80% | ~82% |
| Edge cases | 75% | ~78% |

### Excluding Code from Coverage

```python
def debug_function():  # pragma: no cover
    """This function is excluded from coverage."""
    pass

if __name__ == "__main__":  # Automatically excluded
    main()
```

---

## CI/CD Integration

### GitHub Actions Workflow

The test suite runs automatically on:
- Push to any branch
- Pull request creation/update

```yaml
# .github/workflows/python-app.yml
- name: Run tests with coverage
  run: |
    pytest --cov=. --cov-report=xml --cov-fail-under=85

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
```

### Pre-commit Hooks (Optional)

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest --tb=short -q
        language: system
        types: [python]
        pass_filenames: false
```

### Local CI Simulation

```bash
# Run the same checks as CI
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
pytest --cov=. --cov-fail-under=85
```

---

## Debugging Tests

### Verbose Output

```bash
# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb
```

### Running Specific Failed Tests

```bash
# Run only failed tests from last run
pytest --lf

# Run failed tests first, then rest
pytest --ff
```

### Test Discovery Issues

```bash
# Show what tests would be collected
pytest --collect-only

# Show why tests aren't being collected
pytest --collect-only -v
```

---

## Best Practices

### Do's

- Write tests before fixing bugs (TDD)
- Use descriptive test names
- Keep tests independent (no shared state)
- Use fixtures for common setup
- Test edge cases and error conditions
- Mock external dependencies

### Don'ts

- Don't test implementation details
- Don't use `time.sleep()` in tests (mock it)
- Don't hardcode file paths (use fixtures)
- Don't ignore flaky tests (fix them)
- Don't skip tests without reason

### Test Documentation

```python
def test_checkpoint_recovery_after_interruption(self, temp_dir):
    """Test that processing resumes correctly after interruption.

    This test verifies that:
    1. Checkpoint file is created during processing
    2. Progress is saved when interrupted
    3. Processing resumes from the correct batch
    4. No data is duplicated after recovery

    Regression test for issue #42.
    """
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Tests not discovered | Check file/function naming (`test_*.py`, `test_*`) |
| Import errors | Run from project root, check `PYTHONPATH` |
| Fixture not found | Check fixture is in `conftest.py` or imported |
| Slow tests | Use `-m "not slow"` or mock time-consuming operations |
| Flaky tests | Check for race conditions, use proper mocking |

### Getting Help

```bash
# Show pytest help
pytest --help

# Show available markers
pytest --markers

# Show available fixtures
pytest --fixtures
```
