# CLAUDE.md - AI Assistant Guide

## Project Overview

This is a **Stock Data Retrieval and Notion Integration System** that:

- Retrieves historical stock data for 6,626+ tickers from the Polygon API
- Processes data in 5-year time chunks (2000-2024)
- Saves results to a Notion database for analysis and tracking
- Handles batch processing with checkpointing and error recovery

**Purpose**: Enable bulk historical stock data collection and storage in a structured, queryable Notion database.

**Status**: The system is operational with 55+ batches already processed (~82% complete).

## Architecture

### System Design

```TEXT
Ticker List (JSON) → Batch Processor → Polygon API → Data Aggregation → Notion Upload
                                ↓
                        Checkpoint System
                                ↓
                        Batch Files (JSON)
```

### Key Design Principles

1. **Batch Processing**: Process 100 tickers at a time to manage API rate limits
2. **Checkpointing**: Save progress every 10 batches for recovery
3. **Time Chunking**: Split historical data into 5-year periods
4. **Graceful Degradation**: Track both successful and failed data retrievals
5. **Separation of Concerns**: Data retrieval separate from Notion upload

## File Structure

### Core Execution Scripts

```TEXT
/home/user/polygon_stock_api/
├── execute_stock_retrieval.py          # Main production executor (400+ lines)
├── production_stock_retrieval.py       # Production retrieval system (350+ lines)
├── stock_notion_retrieval.py           # Notion integration version (375+ lines)
├── execute_complete_production.py      # Complete pipeline runner (130+ lines)
└── upload_to_notion.py                 # Notion upload handler (minimal)
```

### Documentation

```TEXT
├── PRODUCTION_GUIDE.md                 # Production deployment instructions
├── STATUS_REPORT.md                    # Current system status and progress
└── CLAUDE.md                           # This file - AI assistant guide
```

### Data Files

```TEXT
├── all_tickers.json                    # List of 6,626+ stock tickers
├── batch_NNNN_notion.json              # Processed batch data (55+ files)
├── checkpoint.json                     # Recovery checkpoint
├── execution_summary.json              # Execution statistics
├── production_run.log                  # Detailed execution logs
└── execution.log                       # General execution logs
```

### CI/CD

```TEXT
.github/workflows/
├── python-app.yml                      # Run tests and linting
└── python-publish.yml                  # Package publishing workflow
```

## Core Components

### 1. `execute_stock_retrieval.py` (Primary Script)

**Class**: `StockDataExecutor`

**Key Methods**:

- `load_tickers()` - Load ticker list from JSON
- `execute_batch(batch, batch_num, total_batches)` - Process 100 tickers
- `create_notion_pages(batch_data, batch_num)` - Format for Notion API
- `generate_upload_script(total_batches)` - Create upload helper script
- `run()` - Main execution loop

**Configuration**:

```python
self.ticker_file = "/mnt/user-data/outputs/all_tickers.json"
self.data_source_id = "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
self.batch_size = 100
```

**Time Periods**:

```python
self.periods = [
    {"from": "2020-01-01", "to": "2024-11-23", "label": "2020-2024"},
    {"from": "2015-01-01", "to": "2019-12-31", "label": "2015-2019"},
    {"from": "2010-01-01", "to": "2014-12-31", "label": "2010-2014"},
    {"from": "2005-01-01", "to": "2009-12-31", "label": "2005-2009"},
    {"from": "2000-01-01", "to": "2004-12-31", "label": "2000-2004"}
]
```

### 2. `production_stock_retrieval.py` (Production System)

**Class**: `ProductionStockRetriever`

**Key Features**:

- Rate limiting with `time.sleep(0.01)` (10ms between API calls)
- Progress tracking with detailed logging
- Checkpoint saving every 10 batches
- Error handling and recovery
- Notion upload script generation

**Polygon API Integration Point**:

```python
def get_polygon_data(self, ticker, period):
    """
    IMPORTANT: This is where actual Polygon API calls should be made
    Currently returns placeholder data

    In production, replace with:
    response = mcp_polygon.get_aggs(
        ticker=ticker,
        multiplier=1,
        timespan="day",  # Try minute → hour → day
        from_=period["from"],
        to=period["to"],
        adjusted=True,
        sort="asc",
        limit=50000
    )
    """
```

### 3. `stock_notion_retrieval.py` (Notion-Focused Version)

**Class**: `StockDataNotionRetriever`

**Differences from production_stock_retrieval.py**:

- Uses `@dataclass` for `TimeChunk` definition
- More detailed Notion database structure setup
- Includes `create_notion_database()` method
- Different checkpoint file naming

### 4. `execute_complete_production.py` (Pipeline Runner)

**Purpose**: Orchestrates the complete workflow

1. Runs production retrieval script
2. Counts generated batch files
3. Uploads to Notion (currently simulated)
4. Generates final report

**Usage**: Single command to run the entire pipeline

## Data Structures

### Ticker File Format

```json
["AAPL", "MSFT", "GOOGL", "AMZN", ...]
```

### Batch Output Format

```json
{
  "data_source_id": "7c5225aa-429b-4580-946e-ba5b1db2ca6d",
  "batch_number": 1,
  "record_count": 500,
  "timestamp": "2025-11-24T05:01:58.387878",
  "pages": [
    {
      "properties": {
        "Ticker": "AAPL",
        "Period": "2020-2024",
        "Has Data": "__YES__",
        "Batch Number": 1,
        "date:Date:start": "2020-01-01",
        "date:Date:is_datetime": 0,
        "date:Retrieved At:start": "2025-11-24T05:01:53.007369",
        "date:Retrieved At:is_datetime": 1,
        "Open": 150.25,
        "High": 155.50,
        "Low": 149.00,
        "Close": 154.30,
        "Volume": 50000000,
        "VWAP": 152.45,
        "Transactions": 450000,
        "Data Points": 252,
        "Timespan": "day"
      }
    }
  ]
}
```

### Notion Database Schema

| Field | Type | Description |
|-------|------|-------------|
| Ticker | Title | Stock symbol |
| Date | Date | Start date of period |
| Period | Select | 5-year chunk (2020-2024, etc.) |
| Open | Number | Opening price |
| High | Number | Highest price |
| Low | Number | Lowest price |
| Close | Number | Closing price |
| Volume | Number | Trading volume |
| VWAP | Number | Volume Weighted Average Price |
| Transactions | Number | Number of transactions |
| Data Points | Number | Count of data points retrieved |
| Has Data | Checkbox | Whether data was available |
| Timespan | Select | Resolution (minute/hour/day) |
| Retrieved At | Date | When data was retrieved |
| Batch Number | Number | Processing batch number |

**Notion Database URL**: <https://www.notion.so/638a8018f09d4e159d6d84536f411441>
**Data Source ID**: `7c5225aa-429b-4580-946e-ba5b1db2ca6d`

## Development Workflow

### Running the System

#### Option 1: Full Production Run

```bash
cd /mnt/user-data/outputs
python execute_complete_production.py
```

#### Option 2: Retrieval Only

```bash
python production_stock_retrieval.py
# or
python execute_stock_retrieval.py
```

#### Option 3: Upload Only

```bash
python upload_to_notion.py
```

### Monitoring Progress

**View logs**:

```bash
tail -f /mnt/user-data/outputs/production_run.log
# or
tail -f /mnt/user-data/outputs/execution.log
```

**Check checkpoint**:

```bash
cat /mnt/user-data/outputs/checkpoint.json
```

**Count processed batches**:

```bash
ls -1 batch_*_notion.json | wc -l
```

### Recovery After Interruption

- Check the last successful batch:

```bash
cat checkpoint.json
```

- Modify script to resume from that batch:

```python
# In the script, adjust the batch range:
for batch_num in range(LAST_CHECKPOINT + 1, total_batches + 1):
    # ... process batch
```

- Re-run the script

## Key Conventions

### Coding Standards

1. **Logging**: Use structured logging with levels

   ```python
   logger.info("✅ Success message")
   logger.warning("⚠️ Warning message")
   logger.error("❌ Error message")
   ```

2. **Progress Indicators**: Use emojis for visual clarity
   - 📊 Processing/Stats
   - ✅ Success
   - ❌ Error
   - ⚠️ Warning
   - 💾 Saving
   - 🚀 Starting
   - ⏱️ Timing

3. **File Paths**: Use absolute paths

   ```python
   "/mnt/user-data/outputs/filename.json"  # Good
   "outputs/filename.json"                 # Avoid
   ```

4. **Batch Numbering**: 4-digit zero-padded

   ```python
   f"batch_{batch_num:04d}_notion.json"  # batch_0001_notion.json
   ```

5. **Date Formats**: ISO 8601

   ```python
   datetime.now().isoformat()  # "2025-11-24T05:01:53.007369"
   ```

### Naming Conventions

- **Scripts**: `verb_noun.py` (e.g., `execute_stock_retrieval.py`)
- **Classes**: `PascalCase` (e.g., `StockDataExecutor`)
- **Methods**: `snake_case` (e.g., `load_tickers()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DATA_SOURCE_ID`)

### Error Handling Patterns

```python
try:
    # Main logic
    result = process_data()

except KeyboardInterrupt:
    logger.warning("\n⚠️ Process interrupted by user")
    save_checkpoint()

except Exception as e:
    logger.error(f"❌ Error: {e}")
    save_checkpoint()
    raise
```

## Integration Points

### Polygon API Integration

**Location**: `get_polygon_data()` method in retrieval scripts

**Current State**: Returns placeholder data
**Required Action**: Replace with actual `mcp_polygon.get_aggs()` calls

**Implementation Pattern**:

```python
def get_polygon_data(self, ticker, period):
    try:
        # Determine timespan based on date range
        timespan = "day"  # or "hour" or "minute"

        # Call Polygon API
        response = mcp_polygon.get_aggs(
            ticker=ticker,
            multiplier=1,
            timespan=timespan,
            from_=period["from"],
            to=period["to"],
            adjusted=True,
            sort="asc",
            limit=50000
        )

        # Parse response
        if response and response.get("results"):
            results = response["results"]
            return {
                "ticker": ticker,
                "period": period["label"],
                "has_data": True,
                "open": results[0].get("o"),
                "high": max(r.get("h") for r in results),
                "low": min(r.get("l") for r in results),
                "close": results[-1].get("c"),
                "volume": sum(r.get("v", 0) for r in results),
                "vwap": sum(r.get("vw", 0) for r in results) / len(results),
                "transactions": sum(r.get("n", 0) for r in results),
                "data_points": len(results),
                "timespan": timespan
            }
    except Exception as e:
        logger.warning(f"⚠️ Failed to get data for {ticker}: {e}")

    # Return null data structure
    return {"ticker": ticker, "period": period["label"], "has_data": False, ...}
```

**Rate Limiting**: Current implementation uses 10ms delays (`time.sleep(0.01)`)

**Data Resolution Strategy**:

1. Try minute data for recent periods (last 30 days)
2. Fall back to hour data for medium-term (6 months)
3. Use day data for historical (2+ years)

### Notion API Integration

**Location**: `save_batch_to_notion()` and `create_notion_pages()` methods

**Current State**: Saves to JSON files for later upload
**Required Action**: Implement actual Notion API calls

**Implementation Pattern**:

```python
# Use Notion API to create pages
notion.create_pages(
    parent={
        "type": "data_source_id",
        "data_source_id": "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
    },
    pages=notion_pages
)
```

**Notion API Limits**:

- 100 pages per create request
- Rate limiting required (use delays)

## Current System State

### Progress Summary

- **Total Tickers**: 6,626
- **Batch Size**: 100 tickers/batch
- **Total Batches**: 67
- **Completed Batches**: 55 (82%)
- **Remaining Batches**: 12
- **Records Generated**: ~27,500+

### Generated Files

- 55+ batch files in `/mnt/user-data/outputs/batch_NNNN_notion.json`
- Each file ~170KB, contains 500 records (100 tickers × 5 periods)
- Checkpoint saved at regular intervals
- Execution logs available

### Next Steps

1. Complete remaining 12 batches
2. Integrate actual Polygon API credentials
3. Upload all batches to Notion database
4. Verify data in Notion

## Troubleshooting

### Common Issues

#### 1. "File not found: all_tickers.json"

**Solution**: Ensure ticker file exists at correct path

```bash
ls -l /mnt/user-data/outputs/all_tickers.json
# or check alternate location
ls -l /mnt/user-data/uploads/all_tickers.json
```

#### 2. Script hangs or runs slowly

**Possible Causes**:

- Polygon API rate limiting
- Network latency
- Large result sets

**Solution**: Adjust rate limiting delay

```python
time.sleep(0.01)  # Increase to 0.05 or 0.1 if needed
```

#### 3. Out of memory errors

**Solution**: Process fewer tickers per batch

```python
self.batch_size = 50  # Reduce from 100
```

#### 4. Checkpoint not saving

**Solution**: Check write permissions

```bash
ls -ld /mnt/user-data/outputs/
# Ensure directory is writable
```

### Log Analysis

**Search for errors**:

```bash
grep "ERROR" production_run.log
grep "❌" production_run.log
```

**Check progress**:

```bash
grep "Progress:" production_run.log | tail -5
```

**View checkpoint history**:

```bash
grep "Checkpoint saved" production_run.log
```

## Testing

### CI/CD Pipeline

- **GitHub Actions**: Configured in `.github/workflows/`
- **Linting**: flake8 with standard Python conventions
- **Testing**: pytest (ensure tests are written)

### Local Testing

**Test with small subset**:

```python
# Modify load_tickers() temporarily
self.tickers = self.tickers[:10]  # Test with 10 tickers only
```

**Validate batch output**:

```python
import json
with open('batch_0001_notion.json') as f:
    data = json.load(f)
    assert data['record_count'] > 0
    assert 'pages' in data
```

## Performance Considerations

### Current Performance

- **API Calls**: ~33,000 total (6,626 tickers × 5 periods)
- **Rate**: ~100 API calls/min (with 10ms delay)
- **Est. Runtime**: 5-6 minutes for retrieval
- **Disk Usage**: ~9.4 MB for 55 batch files

### Optimization Opportunities

- **Parallel Processing**: Process multiple batches concurrently
- **Caching**: Cache API responses to avoid duplicate calls
- **Compression**: Compress batch files to save disk space
- **Database**: Use local SQLite before Notion upload

## Future Development

### Recommended Enhancements

1. **Resume Capability**
   - Add command-line flag to resume from checkpoint
   - Automatic detection of last completed batch

2. **Validation Layer**
   - Validate ticker symbols before processing
   - Check for data completeness
   - Verify Notion uploads succeeded

3. **Configuration File**
   - Move hardcoded values to config.json or .env
   - Support multiple Notion databases
   - Configurable time periods

4. **Monitoring Dashboard**
   - Real-time progress tracking
   - Success/failure metrics
   - Performance statistics

5. **Error Recovery**
   - Retry failed API calls with exponential backoff
   - Separate failed tickers for later reprocessing
   - Alert system for critical failures

6. **Data Analysis**
   - Calculate additional metrics (RSI, moving averages)
   - Detect anomalies in data
   - Generate summary statistics

### Code Structure Improvements

1. **Consolidate Scripts**: Merge the three similar retrieval scripts
2. **Extract Configuration**: Create a `config.py` module
3. **Add Type Hints**: Use `typing` module throughout
4. **Unit Tests**: Add comprehensive test coverage
5. **Documentation**: Add docstrings to all methods

## Working with This Codebase

### For AI Assistants

When modifying this codebase:

1. **Read First**: Always read the relevant script before making changes
2. **Preserve Logging**: Maintain the detailed logging structure
3. **Test Incrementally**: Test changes with small ticker subsets first
4. **Update Documentation**: Modify this file when making significant changes
5. **Maintain Checkpoints**: Don't break the checkpoint/recovery system
6. **Follow Conventions**: Use the established naming and formatting patterns
7. **Handle Errors**: Wrap new code in try-except with appropriate logging
8. **Comment Integration Points**: Clearly mark where external APIs are called

### Making Changes

#### Adding a New Time Period

```python
# In any retrieval script
self.periods.append({
    "from": "1995-01-01",
    "to": "1999-12-31",
    "label": "1995-1999"
})
```

#### Changing Batch Size

```python
# In __init__ method
self.batch_size = 200  # Change from 100
```

#### Adding New Data Fields

```python
# In create_notion_pages() or similar
properties["NewField"] = calculated_value

# Also update Notion database schema
# And update this documentation
```

### Git Workflow

**Current Branch**: `claude/claude-md-mid6yfw15j2ih2jl-0194JGHDrvZw6pkb87MEFwX6`

**Commit Message Format**:

```TEXT
feat: Add new feature description
fix: Fix bug description
docs: Update documentation
refactor: Refactor code description
```

**Before Committing**:

- Test changes with small dataset
- Check logs for errors
- Verify batch files are valid JSON
- Update relevant documentation

## Resources

### Key URLs

- **Notion Database**: <https://www.notion.so/638a8018f09d4e159d6d84536f411441>
- **Polygon API Docs**: <https://polygon.io/docs/stocks/getting-started>
- **Notion API Docs**: <https://developers.notion.com/>

### Important IDs

- **Data Source ID**: `7c5225aa-429b-4580-946e-ba5b1db2ca6d`
- **Collection URI**: `collection://7c5225aa-429b-4580-946e-ba5b1db2ca6d`

### File Locations

- **Ticker File**: `/mnt/user-data/uploads/all_tickers.json` or `/mnt/user-data/outputs/all_tickers.json`
- **Output Directory**: `/mnt/user-data/outputs/`
- **Logs**: `/mnt/user-data/outputs/production_run.log` and `execution.log`

---

**Last Updated**: 2025-11-24
**Version**: 1.0
**Maintainer**: Automated system with human oversight
