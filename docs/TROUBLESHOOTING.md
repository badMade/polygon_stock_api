# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the Stock Data Retrieval System.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [API Errors](#api-errors)
- [File System Errors](#file-system-errors)
- [Data Quality Issues](#data-quality-issues)
- [Performance Issues](#performance-issues)
- [Recovery Procedures](#recovery-procedures)
- [Getting Help](#getting-help)

---

## Quick Diagnostics

### Health Check Commands

```bash
# Check Python environment
python --version
pip list | grep -E "(pytest|requests)"

# Verify file permissions
ls -la /path/to/data/directory

# Check environment variables
echo $POLYGON_API_KEY | head -c 10
echo $STOCK_APP_DATA_DIR

# Test API connectivity
curl -s "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-02?apiKey=$POLYGON_API_KEY" | head -c 200

# Check disk space
df -h /path/to/data/directory

# View recent logs
tail -50 production_run.log
```

### System Status Check

```bash
# Check checkpoint status
cat checkpoint.json | python -m json.tool

# Count processed batches
ls -1 batch_*_notion.json 2>/dev/null | wc -l

# Check for errors in logs
grep -i "error\|exception\|failed" production_run.log | tail -20
```

---

## API Errors

### Polygon API Errors

#### 401 Unauthorized

**Symptoms:**
```
Error: 401 Unauthorized
{"status": "ERROR", "error": "Invalid API key"}
```

**Causes:**
- Invalid or expired API key
- API key not set in environment
- Typo in API key

**Solutions:**
```bash
# Verify API key is set
echo $POLYGON_API_KEY

# Test API key directly
curl "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-02?apiKey=$POLYGON_API_KEY"

# Re-export if needed
export POLYGON_API_KEY="your_correct_key"
```

#### 403 Forbidden

**Symptoms:**
```
Error: 403 Forbidden
{"status": "ERROR", "error": "Not authorized"}
```

**Causes:**
- Free tier limitations
- Requesting data outside plan limits
- Account suspended

**Solutions:**
- Check your Polygon.io plan limits
- Upgrade plan if needed
- Contact Polygon support for account issues

#### 429 Too Many Requests

**Symptoms:**
```
Error: 429 Too Many Requests
{"status": "ERROR", "error": "Rate limit exceeded"}
```

**Causes:**
- Making requests too quickly
- Rate limit delay too low

**Solutions:**
```python
# Increase rate limit delay in code
time.sleep(0.1)  # 100ms instead of 10ms

# Or set environment variable
export RATE_LIMIT_DELAY=0.1
```

#### Empty Results

**Symptoms:**
```json
{"results": [], "resultsCount": 0, "status": "OK"}
```

**Causes:**
- No trading data for the period (weekends, holidays)
- Ticker delisted or renamed
- Date range too old for plan
- Invalid ticker symbol

**Solutions:**
```bash
# Try a known good ticker and recent date
curl "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-03?apiKey=$POLYGON_API_KEY"

# Check if ticker exists
curl "https://api.polygon.io/v3/reference/tickers/AAPL?apiKey=$POLYGON_API_KEY"
```

#### Network Timeout

**Symptoms:**
```
ConnectionError: Connection timed out
requests.exceptions.Timeout
```

**Causes:**
- Network connectivity issues
- API server overloaded
- Firewall blocking requests

**Solutions:**
```bash
# Test basic connectivity
ping api.polygon.io

# Test with longer timeout
curl --max-time 30 "https://api.polygon.io/..."

# Check firewall rules
# Ensure outbound HTTPS (443) is allowed
```

---

### Notion API Errors

#### 401 Unauthorized

**Symptoms:**
```
Error: 401 Unauthorized
{"code": "unauthorized", "message": "API token is invalid"}
```

**Solutions:**
```bash
# Verify token format (should start with "secret_")
echo $NOTION_API_KEY | head -c 10

# Regenerate token at https://www.notion.so/my-integrations
```

#### 403 Forbidden - Object Not Found

**Symptoms:**
```
Error: 403 Forbidden
{"code": "object_not_found", "message": "Could not find database"}
```

**Causes:**
- Database not shared with integration
- Wrong database ID
- Integration deleted

**Solutions:**
1. Open database in Notion
2. Click "..." menu → "Add connections"
3. Add your integration
4. Verify database ID in URL

#### 400 Validation Error

**Symptoms:**
```
Error: 400 Bad Request
{"code": "validation_error", "message": "property does not exist"}
```

**Causes:**
- Property name mismatch
- Wrong property type
- Missing required property

**Solutions:**
- Compare batch file properties with database schema
- Check for typos in property names
- Ensure all required fields are present

---

## File System Errors

### FileNotFoundError

**Symptoms:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/path/to/tickers.json'
```

**Causes:**
- Ticker file doesn't exist
- Wrong path configured
- Path contains typo

**Solutions:**
```bash
# Check if file exists
ls -la /mnt/user-data/uploads/all_tickers.json

# Verify configured path
grep "ticker_file" *.py

# Create file if missing
echo '["AAPL", "MSFT"]' > all_tickers.json
```

### PermissionError

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/path/to/output'
```

**Causes:**
- No write permission to directory
- Directory owned by different user
- Read-only filesystem

**Solutions:**
```bash
# Check permissions
ls -la /path/to/output

# Fix permissions
chmod 755 /path/to/output
chown $USER:$USER /path/to/output

# Use different directory
export STOCK_APP_DATA_DIR=/tmp/stock_data
```

### Disk Full

**Symptoms:**
```
OSError: [Errno 28] No space left on device
```

**Causes:**
- Disk full
- Quota exceeded
- Too many batch files

**Solutions:**
```bash
# Check disk space
df -h .

# Find large files
du -sh batch_*.json | sort -h | tail -10

# Clean up old batches (if safe)
# WARNING: Only do this if you have backups!
# rm batch_old_*.json
```

### JSON Decode Error

**Symptoms:**
```
json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Causes:**
- Empty file
- Corrupted JSON
- Wrong file format

**Solutions:**
```bash
# Check file contents
head -c 100 problematic_file.json

# Validate JSON
python -m json.tool problematic_file.json

# Regenerate file if corrupted
```

---

## Data Quality Issues

### Missing Data for Ticker

**Symptoms:**
- "Has Data" is False for many tickers
- Data points count is 0

**Causes:**
- Ticker doesn't exist
- No data for time period
- API plan limitations

**Solutions:**
```python
# Verify ticker exists
# Check Polygon ticker reference API

# Try different time period
# Some tickers only have recent data

# Check for ticker renames/mergers
```

### Price Anomalies

**Symptoms:**
- Extremely high/low prices
- Negative prices
- Zero prices

**Causes:**
- Stock splits not adjusted
- Data errors from source
- Currency conversion issues

**Solutions:**
```python
# Use adjusted=true in API calls
# Validate data before saving
# Flag anomalies for manual review
```

### Duplicate Entries

**Symptoms:**
- Same ticker/period appears multiple times
- Batch files overlap

**Causes:**
- Checkpoint not saved
- Process restarted incorrectly
- Batch overlap

**Solutions:**
```bash
# Check for duplicates in batch files
cat batch_*.json | grep -o '"Ticker":"[^"]*"' | sort | uniq -c | sort -rn | head

# Remove duplicate batch files
# Start from clean checkpoint
```

---

## Performance Issues

### Slow Processing

**Symptoms:**
- Processing takes longer than expected
- ETA keeps increasing

**Causes:**
- Rate limiting too conservative
- Network latency
- Large response sizes

**Solutions:**
```python
# Decrease rate limit delay (if plan allows)
time.sleep(0.005)  # 5ms instead of 10ms

# Process in parallel (advanced)
# Use async requests

# Filter unnecessary data
```

### High Memory Usage

**Symptoms:**
- Process killed by OOM
- System becomes unresponsive

**Causes:**
- Batch size too large
- Memory leak
- Accumulating data

**Solutions:**
```python
# Reduce batch size
self.batch_size = 50  # Instead of 100

# Clear data between batches
del pages
gc.collect()

# Monitor memory
import tracemalloc
tracemalloc.start()
```

### Checkpoint Not Saving

**Symptoms:**
- Progress lost after restart
- Checkpoint file empty or outdated

**Causes:**
- Write permission issue
- Process killed before save
- Checkpoint interval too high

**Solutions:**
```python
# Force checkpoint save
retriever.save_checkpoint(batch_num)

# Reduce checkpoint interval
CHECKPOINT_INTERVAL = 5  # Save every 5 batches

# Check file after save
cat checkpoint.json
```

---

## Recovery Procedures

### Resume After Crash

```bash
# 1. Check last checkpoint
cat checkpoint.json

# 2. Note the last completed batch
# Example: {"last_batch": 45, "processed": 4500}

# 3. Modify script to resume from batch 46
# Or let automatic checkpoint recovery handle it

# 4. Restart processing
python production_stock_retrieval.py
```

### Recover Corrupted Checkpoint

```bash
# 1. Check if checkpoint is valid JSON
python -m json.tool checkpoint.json

# 2. If corrupted, check batch files
ls -lt batch_*_notion.json | head -5

# 3. Determine last good batch from files
# batch_0045_notion.json means batch 45 completed

# 4. Create new checkpoint manually
echo '{"last_batch": 45, "processed": 4500, "timestamp": "2024-01-01T00:00:00"}' > checkpoint.json
```

### Rebuild Missing Batch

```bash
# 1. Identify missing batch
ls batch_*_notion.json | sort -V

# 2. Calculate ticker range for batch
# Batch 45 = tickers 4400-4499 (with batch_size=100)

# 3. Create custom ticker list
python -c "
import json
with open('all_tickers.json') as f:
    tickers = json.load(f)
missing = tickers[4400:4500]
with open('missing_tickers.json', 'w') as f:
    json.dump(missing, f)
"

# 4. Process just that batch
# Modify script to use missing_tickers.json
```

### Full Reset

```bash
# WARNING: This deletes all progress!

# 1. Backup existing data
mkdir backup_$(date +%Y%m%d)
cp batch_*.json checkpoint.json backup_*/

# 2. Remove all generated files
rm batch_*_notion.json
rm checkpoint.json
rm execution_summary.json

# 3. Start fresh
python production_stock_retrieval.py
```

---

## Getting Help

### Collecting Debug Information

Before asking for help, gather:

```bash
# System info
uname -a
python --version
pip freeze > requirements_actual.txt

# Error context
tail -100 production_run.log > error_context.log

# Configuration (remove secrets!)
cat checkpoint.json
ls -la batch_*.json | wc -l

# Test results
pytest tests/ -v --tb=short 2>&1 | tail -50
```

### Log Analysis

```bash
# Find all errors
grep -i "error" production_run.log

# Find all warnings
grep -i "warning\|⚠️" production_run.log

# Track progress over time
grep "Progress:" production_run.log | tail -20

# Find specific ticker issues
grep "PROBLEMATIC_TICKER" production_run.log
```

### Reporting Issues

When reporting issues, include:

1. **What you expected** - Desired behavior
2. **What happened** - Actual behavior
3. **Steps to reproduce** - Commands run
4. **Error messages** - Full error text
5. **Environment** - OS, Python version, dependencies
6. **Logs** - Relevant log excerpts (sanitized)

### Resources

- [API Setup Guide](API_SETUP.md)
- [Testing Guide](TESTING.md)
- [Production Guide](../PRODUCTION_GUIDE.md)
- [Claude Guide](../CLAUDE.md)
- [Polygon API Docs](https://polygon.io/docs/stocks/getting-started)
- [Notion API Docs](https://developers.notion.com/)
