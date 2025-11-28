# Polygon Stock API Utilities

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

- `data_source_id`: `7c5225aa-429b-4580-946e-ba5b1db2ca6d`
- Database URL: `https://www.notion.so/638a8018f09d4e159d6d84536f411441`

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

| Command | Description |
|---------|-------------|
| `pytest` | Run full test suite |
| `pytest -v` | Run tests with verbose output |
| `pytest tests/test_production_stock_retrieval.py` | Run specific test file |
| `flake8 .` | Run linter |
| `python -m py_compile *.py` | Verify syntax |

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

## License

See LICENSE file for details.
