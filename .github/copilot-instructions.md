# Copilot Instructions

## Project Overview

This is a **Stock Data Retrieval and Notion Integration System** that:
- Retrieves historical stock data for 6,626+ tickers from the Polygon API
- Processes data in 5-year time chunks (2000-2024)
- Saves results to a Notion database for analysis and tracking
- Handles batch processing with checkpointing and error recovery

## Repository Structure

### Core Scripts
- `execute_stock_retrieval.py` - Main production executor
- `production_stock_retrieval.py` - Production retrieval system
- `stock_notion_retrieval.py` - Combined stock retrieval and Notion integration script
- `execute_complete_production.py` - Complete pipeline runner
- `upload_to_notion.py` - Notion upload handler

### Key Data Files
- `all_tickers.json` - List of stock tickers to process
- `batch_NNNN_notion.json` - Processed batch data files
- `checkpoint.json` - Recovery checkpoint

## Coding Conventions

### Style Guidelines
- **Python**: Follow PEP 8 style guidelines
- **Logging**: Use structured logging with emoji indicators:
  - ✅ Success, ❌ Error, ⚠️ Warning, 📊 Processing, 💾 Saving, 🚀 Starting
- **File paths**: Use absolute paths when working with data files
- **Batch numbering**: Use 4-digit zero-padded format (e.g., `batch_0001_notion.json`)
- **Date formats**: Use ISO 8601 format

### Naming Conventions
- **Scripts**: `verb_noun.py` (e.g., `execute_stock_retrieval.py`)
- **Classes**: `PascalCase` (e.g., `StockDataExecutor`)
- **Methods**: `snake_case` (e.g., `load_tickers()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DATA_SOURCE_ID`)

### Error Handling
Always use try-except blocks with proper logging and checkpoint saving:
```python
try:
    result = process_data()
except KeyboardInterrupt:
    logger.warning("\n⚠️ Process interrupted by user")
    save_checkpoint()
except Exception as e:
    logger.error(f"❌ Error: {e}")
    save_checkpoint()
    raise
```

## Build and Test Commands

```bash
# Install test dependencies
pip install flake8 pytest

# Install project dependencies (if requirements.txt exists)
pip install -r requirements.txt

# Run linting
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Run tests
pytest
```

## Integration Points

### Polygon API
- Data retrieval happens in `get_polygon_data()` methods
- Rate limiting: 10ms delays between API calls (`time.sleep(0.01)`)
- Data resolution: minute → hour → day (fallback strategy)

### Notion API
- Upload functions in `save_batch_to_notion()` and `create_notion_pages()`
- Data Source ID: `7c5225aa-429b-4580-946e-ba5b1db2ca6d`
- Batch limit: 100 pages per create request

## Best Practices When Making Changes

1. **Read First**: Always read the relevant script before making changes
2. **Preserve Logging**: Maintain the detailed logging structure
3. **Test Incrementally**: Test changes with small ticker subsets first
4. **Maintain Checkpoints**: Don't break the checkpoint/recovery system
5. **Handle Errors**: Wrap new code in try-except with appropriate logging
6. **Update Documentation**: Update CLAUDE.md when making significant changes

## Common Tasks

### Adding a New Time Period
```python
self.periods.append({
    "from": "1995-01-01",
    "to": "1999-12-31",
    "label": "1995-1999"
})
```

### Testing with Small Subset
```python
# Modify load_tickers() temporarily
self.tickers = self.tickers[:10]  # Test with 10 tickers only
```

## Additional Context

For more detailed documentation, see:
- `CLAUDE.md` - Comprehensive AI assistant guide
- `PRODUCTION_GUIDE.md` - Production deployment instructions
- `STATUS_REPORT.md` - Current system status and progress
