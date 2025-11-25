# Polygon Stock API Utilities

## Overview

This repository contains lightweight utilities for simulating large-scale stock data retrieval and exporting the results to Notion. The scripts focus on predictable, testable behavior using stubbed Polygon responses so you can validate workflows without external APIs.

## Installation

Install dependencies into your environment:

```bash
pip install -r requirements.txt
```

The tools are pure-Python and require no additional services.

## Usage

### Retrieve stock data

`execute_stock_retrieval.py` simulates pulling historical aggregates for thousands of tickers and writes Notion-ready batch files to `/mnt/user-data/outputs/`.

```bash
python execute_stock_retrieval.py
```

Key outputs include `notion_batch_*.json` batch files and an execution summary stored alongside the generated upload helper script.

### Production-style retrieval

`production_stock_retrieval.py` mirrors the same flow with logging and checkpoint support for longer runs:

```bash
python production_stock_retrieval.py
```

### Notion upload simulation

`upload_to_notion.py` reads saved batch payloads and emulates page creation logic for downstream processing:

```bash
python upload_to_notion.py
```

### Notion-focused retrieval

`stock_notion_retrieval.py` provides helpers for creating the Notion database schema and formatting Polygon responses into page payloads. Its `StockDataNotionRetriever` class demonstrates loading tickers, chunking time ranges, and composing page properties.

## Testing

Run the full automated suite to validate behavior:

```bash
pytest
```

The tests cover ticker loading, batch processing, Notion payload generation, and the simulated Polygon aggregation logic.

## Project structure

- `execute_stock_retrieval.py` – batch-oriented executor that simulates Polygon data pulls and prepares Notion upload bundles.
- `production_stock_retrieval.py` – production-style variant with richer logging and checkpointing hooks.
- `stock_notion_retrieval.py` – helpers for Notion schema generation and formatting retrieved data.
- `upload_to_notion.py` – emulates uploading prepared batches to Notion.
- `tests/` – Pytest suite validating executors, Notion formatting, and simulated API flows.

## Troubleshooting

- Ensure dependencies are installed if you see `ModuleNotFoundError` errors (e.g., `requests`).
- Verify the `/mnt/user-data/outputs/` directory exists or adjust paths if running in a different environment.
- Re-run `pytest` after making changes to confirm all behaviors remain deterministic.

## Contributing

Keep changes focused and well-tested. New functions and public classes should include clear docstrings, and any external interactions should be simulated or mocked to remain environment-agnostic.
