# Polygon Stock API Utilities

[![Tests](https://github.com/badMade/polygon_stock_api/actions/workflows/python-app.yml/badge.svg)](https://github.com/badMade/polygon_stock_api/actions/workflows/python-app.yml)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)](https://github.com/badMade/polygon_stock_api)

## Project Overview

This repository provides utilities for simulating large-scale historical stock data retrieval from the Polygon API and exporting results to a Notion database. The scripts use stubbed Polygon responses for predictable, testable behavior without requiring external API credentials.

Key capabilities:

- Batch processing of 6,600+ ticker symbols across 5-year time periods
- Notion-ready JSON output with full database schema support
- Checkpointing and recovery for long-running processes
- Comprehensive test coverage for all components

## Tech Stack

- **Language**: Python 3.10+
- **Testing**: pytest
- **Linting**: flake8
- **Dependencies**: requests (for API simulation structure)

## Getting Started

### Prerequisites

- Python 3.10 or later
- pip package manager
- Write access to the repository-local `user-data/outputs/` directory (or set
  the `STOCK_APP_DATA_DIR` environment variable to override the base path).

### Installation

- Clone the repository:

```bash
git clone <repository-url>
cd polygon_stock_api
```

- Install dependencies:

```bash
pip install -r requirements.txt
```

- For development (includes testing and linting tools):

```bash
pip install -r requirements-dev.txt
```

### Configuration

The scripts default to storing inputs and outputs under `user-data/` in the
repository directory. Override the base path by setting `STOCK_APP_DATA_DIR`.

Key file locations:

| Script | Variable | Default Path |
|--------|----------|--------------|
| `execute_stock_retrieval.py` | `ticker_file` | `./user-data/outputs/all_tickers.json` |
| `production_stock_retrieval.py` | `ticker_file` | `./user-data/uploads/all_tickers.json` |
| `stock_notion_retrieval.py` | `ticker_file` | `./user-data/uploads/all_tickers.json` |

**Notion Configuration** (for production use):

Configure via environment variables (see `.env.example`):
- `NOTION_DATA_SOURCE_ID`: Your Notion data source/collection ID
- `NOTION_DATABASE_ID`: Your Notion database ID
- Database URL format: `https://www.notion.so/<YOUR_DATABASE_ID>`

## Usage

### Quick Start

Copy the ticker list and run the basic retrieval (adjust `STOCK_APP_DATA_DIR`
if you need a different base path):

```bash
mkdir -p user-data/outputs
cp all_tickers.json user-data/outputs/all_tickers.json
python execute_stock_retrieval.py
```

### Production Retrieval

For longer runs with logging and checkpoint support:

```bash
mkdir -p user-data/uploads
cp all_tickers.json user-data/uploads/all_tickers.json
python production_stock_retrieval.py
```

### Complete Pipeline

Run the full retrieval and upload simulation:

```bash
python execute_complete_production.py
```

### Notion Upload

Process saved batch files for Notion upload:

```bash
python upload_to_notion.py
```

## Run/Build/Test Commands

### Running Tests

The project includes a comprehensive test suite with 339+ tests covering integration, error recovery, API response handling, data validation, and performance.

| Command | Description |
|---------|-------------|
| `pytest` | Run full test suite (all tests) |
| `pytest -v` | Run tests with verbose output |
| `pytest -m "not slow"` | Run only fast tests (skip performance tests) |
| `pytest -m "integration"` | Run only integration tests |
| `pytest -m "slow"` | Run only performance/slow tests |
| `pytest tests/test_production_stock_retrieval.py` | Run specific test file |
| `pytest tests/test_integration.py::TestEndToEndWorkflow` | Run specific test class |
| `pytest tests/test_performance.py -v` | Run performance tests with verbose output |

### Running Tests with Coverage

| Command | Description |
|---------|-------------|
| `pytest --cov=. --cov-report=term` | Run tests with coverage report |
| `pytest --cov=. --cov-report=html` | Generate HTML coverage report |
| `pytest --cov=. --cov-report=xml --cov-fail-under=85` | Enforce 85% coverage threshold |

### Linting

| Command | Description |
|---------|-------------|
| `flake8 .` | Run linter |
| `pylint *.py` | Run pylint on main scripts |
| `python -m py_compile *.py` | Verify syntax |

### Test Organization

- **Integration tests**: End-to-end workflow testing (`test_integration.py`)
- **Error recovery tests**: Checkpoint recovery, retry logic (`test_error_recovery.py`)
- **API response tests**: Polygon API response handling (`test_api_response_handling.py`)
- **Data validation tests**: Price ranges, dates, duplicates (`test_data_validation.py`)
- **Filesystem tests**: File I/O edge cases (`test_filesystem_edge_cases.py`)
- **Logging tests**: Log output verification (`test_logging_verification.py`)
- **Performance tests**: Speed and scalability baselines (`test_performance.py`)
- **Configuration tests**: Environment variables, settings (`test_configuration.py`)

## Folder Structure

```TEXT
polygon_stock_api/
├── execute_stock_retrieval.py      # Main batch executor
├── execute_complete_production.py  # Full pipeline runner
├── production_stock_retrieval.py   # Production retriever with logging
├── stock_notion_retrieval.py       # Notion-focused retrieval
├── upload_to_notion.py             # Notion upload simulator
├── all_tickers.json                # Source ticker list (6,600+ symbols)
├── tests/
│   ├── conftest.py                 # Shared test fixtures
│   ├── test_execute_stock_retrieval.py
│   ├── test_production_stock_retrieval.py
│   ├── test_stock_notion_retrieval.py
│   ├── test_execute_complete_production.py
│   └── test_upload_to_notion.py
├── batches/                        # Generated batch output files
├── CLAUDE.md                       # AI assistant guide
├── PRODUCTION_GUIDE.md             # Production deployment docs
├── STATUS_REPORT.md                # System status and progress
└── requirements.txt                # Runtime dependencies
└── requirements-dev.txt            # Development/test dependencies
```

## Output Files

After running retrieval scripts, you'll find:

- `batch_NNNN_notion.json`: Notion-ready page data per batch
- `checkpoint.json`: Recovery checkpoint for interrupted runs
- `execution_summary.json`: Statistics and timing information
- `production_run.log`: Detailed execution logs

## Contributing

- Write tests for new functionality
- Ensure all tests pass: `pytest`
- Run linter: `flake8 .`
- Add docstrings to all public functions and classes
- Keep external interactions simulated/mocked

## Troubleshooting

- **ModuleNotFoundError**: Run `pip install -r requirements.txt` (or `pip install -r requirements-dev.txt` for development)
- **FileNotFoundError for ticker file**: Copy `all_tickers.json` to expected path
- **Permission denied on output**: Ensure write access to output directories
- **Tests failing**: Run `pytest -v` for detailed failure information

For more detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Documentation

| Document | Description |
|----------|-------------|
| [API Setup Guide](docs/API_SETUP.md) | Polygon & Notion API credentials and configuration |
| [Testing Guide](docs/TESTING.md) | Test strategy, markers, and running tests |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Production Guide](PRODUCTION_GUIDE.md) | Full production deployment instructions |
| [Claude Guide](CLAUDE.md) | AI assistant integration guide |

### Configuration

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
# Edit .env with your API keys and paths
```

## License

See LICENSE file for details.
