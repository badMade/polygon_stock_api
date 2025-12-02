# API Setup Guide

This guide explains how to set up and configure the Polygon and Notion APIs for the Stock Data Retrieval System.

## Table of Contents

- [Polygon API Setup](#polygon-api-setup)
- [Notion API Setup](#notion-api-setup)
- [Environment Configuration](#environment-configuration)
- [Verifying Your Setup](#verifying-your-setup)
- [Common Issues](#common-issues)

---

## Polygon API Setup

### 1. Create a Polygon Account

1. Go to [Polygon.io](https://polygon.io/)
2. Click "Get Started" or "Sign Up"
3. Create an account (free tier available)

### 2. Get Your API Key

1. Log in to your Polygon dashboard
2. Navigate to **Dashboard** > **API Keys**
3. Copy your API key (starts with a random string)

### 3. API Key Types

| Plan | Rate Limit | Historical Data | Real-time |
|------|------------|-----------------|-----------|
| Free | 5 calls/min | 2 years | No |
| Starter | 100 calls/min | 5 years | Delayed |
| Developer | Unlimited | Full history | Yes |

For this project, **Starter** or higher is recommended for full historical data access.

### 4. Configure the API Key

Set the environment variable:

```bash
# Linux/macOS
export POLYGON_API_KEY="your_api_key_here"

# Windows (PowerShell)
$env:POLYGON_API_KEY="your_api_key_here"

# Windows (CMD)
set POLYGON_API_KEY=your_api_key_here
```

Or add to your `.env` file:

```env
POLYGON_API_KEY=your_api_key_here
```

### 5. API Endpoint Reference

The system uses the **Aggregates (Bars)** endpoint:

```
GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}
```

**Parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `stocksTicker` | Stock symbol | `AAPL` |
| `multiplier` | Size of timespan | `1` |
| `timespan` | Resolution | `day`, `hour`, `minute` |
| `from` | Start date | `2020-01-01` |
| `to` | End date | `2024-12-31` |
| `adjusted` | Adjust for splits | `true` |
| `sort` | Sort order | `asc` |
| `limit` | Max results | `50000` |

**Example Request:**

```bash
curl "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31?adjusted=true&sort=asc&limit=50000&apiKey=YOUR_API_KEY"
```

**Example Response:**

```json
{
  "ticker": "AAPL",
  "queryCount": 21,
  "resultsCount": 21,
  "adjusted": true,
  "results": [
    {
      "v": 45678900,
      "vw": 185.2345,
      "o": 184.50,
      "c": 186.25,
      "h": 187.00,
      "l": 183.75,
      "t": 1704067200000,
      "n": 523456
    }
  ],
  "status": "OK",
  "request_id": "abc123",
  "count": 21
}
```

**Response Fields:**

| Field | Description |
|-------|-------------|
| `v` | Volume |
| `vw` | Volume Weighted Average Price (VWAP) |
| `o` | Open price |
| `c` | Close price |
| `h` | High price |
| `l` | Low price |
| `t` | Timestamp (Unix ms) |
| `n` | Number of transactions |

### 6. Rate Limiting

The system implements rate limiting to avoid API throttling:

```python
time.sleep(0.01)  # 10ms delay = max 100 requests/second
```

**Recommended delays by plan:**

| Plan | Recommended Delay | Requests/Second |
|------|-------------------|-----------------|
| Free | 200ms | 5 |
| Starter | 10ms | 100 |
| Developer | 1ms | 1000 |

---

## Notion API Setup

### 1. Create a Notion Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Fill in:
   - **Name**: "Stock Data Importer"
   - **Associated workspace**: Select your workspace
   - **Capabilities**: Check "Read content", "Update content", "Insert content"
4. Click **Submit**
5. Copy the **Internal Integration Token** (starts with `secret_`)

### 2. Share Database with Integration

1. Open your Notion database
2. Click **"..."** (menu) in the top right
3. Click **"Add connections"**
4. Search for your integration name
5. Click to add it

### 3. Get Database ID

The database ID is in the URL:

```
https://www.notion.so/myworkspace/638a8018f09d4e159d6d84536f411441?v=...
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                  This is your database ID
```

### 4. Configure Notion Credentials

Set environment variables:

```bash
# Linux/macOS
export NOTION_API_KEY="secret_your_token_here"
export NOTION_DATABASE_ID="638a8018f09d4e159d6d84536f411441"

# Or add to .env file
NOTION_API_KEY=secret_your_token_here
NOTION_DATABASE_ID=638a8018f09d4e159d6d84536f411441
```

### 5. Database Schema

Create a Notion database with these properties:

| Property | Type | Description |
|----------|------|-------------|
| Ticker | Title | Stock symbol (e.g., AAPL) |
| Date | Date | Start date of the period |
| Period | Select | Time period label (2020-2024, etc.) |
| Open | Number | Opening price |
| High | Number | Highest price in period |
| Low | Number | Lowest price in period |
| Close | Number | Closing price |
| Volume | Number | Total trading volume |
| VWAP | Number | Volume Weighted Average Price |
| Transactions | Number | Number of transactions |
| Data Points | Number | Count of data points |
| Has Data | Checkbox | Whether data was retrieved |
| Timespan | Select | Data resolution (day/hour/minute) |
| Retrieved At | Date | Timestamp of retrieval |
| Batch Number | Number | Processing batch number |

**Select Options for Period:**

- 2020-2024
- 2015-2019
- 2010-2014
- 2005-2009
- 2000-2004

**Select Options for Timespan:**

- minute
- hour
- day

### 6. Notion API Limits

| Limit | Value |
|-------|-------|
| Requests per second | 3 |
| Pages per create request | 100 |
| Page content size | 2000 blocks |
| Property value size | 2000 characters |

---

## Environment Configuration

### Complete `.env` File

Create a `.env` file in the project root:

```env
# Polygon API Configuration
POLYGON_API_KEY=your_polygon_api_key

# Notion API Configuration
NOTION_API_KEY=secret_your_notion_token
NOTION_DATABASE_ID=638a8018f09d4e159d6d84536f411441

# Application Configuration
STOCK_APP_DATA_DIR=/path/to/data/directory

# Optional: Override defaults
# BATCH_SIZE=100
# RATE_LIMIT_DELAY=0.01
```

### Loading Environment Variables

The system automatically loads from environment:

```python
import os
from pathlib import Path

# Data directory (with fallback)
BASE_DATA_DIR = Path(os.getenv("STOCK_APP_DATA_DIR", Path(__file__).resolve().parent / "user-data"))

# API keys
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
```

### Using python-dotenv (Optional)

Install and use `python-dotenv` to auto-load `.env`:

```bash
pip install python-dotenv
```

```python
from dotenv import load_dotenv
load_dotenv()  # Loads .env file automatically
```

---

## Verifying Your Setup

### Test Polygon API

```bash
# Quick test with curl
curl "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-05?apiKey=$POLYGON_API_KEY"
```

Expected: JSON response with stock data

### Test Notion API

```bash
# Quick test with curl
curl "https://api.notion.com/v1/databases/$NOTION_DATABASE_ID" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2022-06-28"
```

Expected: JSON response with database properties

### Run Integration Tests

```bash
# Run real API tests (requires valid credentials)
pytest tests/test_real_api_integration.py -v -m real_api
```

---

## Common Issues

### Polygon API Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid API key | Check your API key is correct |
| `403 Forbidden` | Plan limitation | Upgrade plan or reduce request scope |
| `429 Too Many Requests` | Rate limit exceeded | Increase delay between requests |
| `404 Not Found` | Invalid ticker | Verify ticker symbol exists |
| Empty `results` | No data for period | Try different date range or timespan |

### Notion API Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid token | Regenerate integration token |
| `403 Forbidden` | No database access | Share database with integration |
| `404 Object not found` | Wrong database ID | Verify database ID from URL |
| `400 Invalid request` | Schema mismatch | Check property names match exactly |
| `409 Conflict` | Duplicate entry | Handle duplicates in code |

### Environment Issues

| Error | Cause | Solution |
|-------|-------|----------|
| `KeyError: 'POLYGON_API_KEY'` | Env var not set | Export variable or add to .env |
| `FileNotFoundError` | Wrong data path | Check `STOCK_APP_DATA_DIR` |
| `PermissionError` | No write access | Check directory permissions |

---

## Security Best Practices

1. **Never commit API keys** - Add `.env` to `.gitignore`
2. **Use environment variables** - Don't hardcode credentials
3. **Rotate keys regularly** - Regenerate keys periodically
4. **Use least privilege** - Only request needed API permissions
5. **Monitor usage** - Check API dashboards for unusual activity

```gitignore
# Add to .gitignore
.env
.env.local
*.key
credentials.json
```

---

## Next Steps

After setting up your APIs:

1. Run the test suite: `pytest tests/ -v`
2. Test with a small batch: Modify `batch_size = 10` temporarily
3. Run production retrieval: `python production_stock_retrieval.py`
4. Upload to Notion: `python upload_to_notion.py`

See [PRODUCTION_GUIDE.md](../PRODUCTION_GUIDE.md) for full production instructions.
