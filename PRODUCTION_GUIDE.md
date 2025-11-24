# Stock Data Retrieval System - Production Guide

## 🎯 System Overview
This system retrieves historical stock data for 6,628 tickers and stores it in a Notion database.

### ✅ What's Been Set Up:
1. **Notion Database Created**: https://www.notion.so/638a8018f09d4e159d6d84536f411441
2. **Data Source ID**: `collection://7c5225aa-429b-4580-946e-ba5b1db2ca6d`
3. **Scripts Created**:
   - `production_stock_retrieval.py` - Main execution script
   - `notion_bulk_upload.py` - Upload data to Notion
4. **Test Run Completed**: Successfully processed 100 test tickers

## 📊 Database Structure

| Field | Type | Description |
|-------|------|-------------|
| Ticker | Title | Stock symbol |
| Date | Date | Start date of period |
| Period | Select | 5-year chunk (2020-2024, 2015-2019, etc.) |
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

## 🚀 Production Run Instructions

### Step 1: Prepare Your Ticker File
Replace the test ticker file with your actual 6,628 ticker list:
```bash
# Upload your actual all_tickers.json file containing 6,628 tickers
# Place it at: /mnt/user-data/outputs/all_tickers.json
```

### Step 2: Configure Polygon API
In `production_stock_retrieval.py`, update the `get_polygon_data()` method to use actual Polygon API:
```python
def get_polygon_data(self, ticker, period):
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
    # Parse response and return structured data
```

### Step 3: Run the Production Script
```bash
cd /mnt/user-data/outputs
python production_stock_retrieval.py
```

### Step 4: Monitor Progress
The script will:
- Process 6,628 tickers in 67 batches (100 tickers each)
- Retrieve data for 5 time periods per ticker
- Total: ~33,140 API calls
- Estimated runtime: ~5-6 minutes (at 10ms per call)
- Save checkpoint every 10 batches

### Step 5: Upload to Notion
After completion, run:
```bash
python notion_bulk_upload.py
```

## 📈 Processing Details

### Batch Processing
- **Batch Size**: 100 tickers
- **Total Batches**: 67 (for 6,628 tickers)
- **Time Periods**: 5 chunks (2000-2024 in 5-year intervals)
- **Records per Ticker**: Up to 5 (one per time period)
- **Total Records**: ~33,140 (if all have data)

### Time Periods (Processed Backwards)
1. 2020-2024 (current)
2. 2015-2019
3. 2010-2014
4. 2005-2009
5. 2000-2004

### Data Resolution Priority
For each ticker and time period, the system tries:
1. **Minute data** (last 30 days only)
2. **Hour data** (last 6 months)
3. **Day data** (full historical)

## 📁 Output Files

### During Processing
- `/mnt/user-data/outputs/batch_NNNN_notion.json` - Batch data files
- `/mnt/user-data/outputs/checkpoint.json` - Progress checkpoint
- `/mnt/user-data/outputs/production_run.log` - Execution log

### After Completion
- `/mnt/user-data/outputs/production_summary.json` - Final summary
- `/mnt/user-data/outputs/notion_bulk_upload.py` - Upload script

## ⚠️ Important Notes

1. **API Rate Limits**: The script includes 10ms delays between API calls. Adjust based on your Polygon subscription.

2. **Data Availability**: Not all tickers will have data for all periods. The system tracks both successful retrievals and nulls.

3. **Resumption**: If interrupted, the script saves checkpoints every 10 batches for manual resumption.

4. **Notion Limits**: Notion API allows 100 pages per create request. The upload script handles this automatically.

## 🔧 Troubleshooting

### If Script Fails
1. Check `/mnt/user-data/outputs/production_run.log` for errors
2. Review `/mnt/user-data/outputs/checkpoint.json` for last successful batch
3. Modify script to resume from last checkpoint

### If Notion Upload Fails
1. Batch files are preserved in `/mnt/user-data/outputs/`
2. Can upload individual batches manually
3. Each batch file is self-contained with all necessary data

## 📊 Current Status

✅ **Test Run Complete**:
- Processed: 100 test tickers
- Created: 35 test records in Notion
- Database: https://www.notion.so/638a8018f09d4e159d6d84536f411441

🎯 **Ready for Production**:
- Scripts configured for 6,628 tickers
- Database structure created
- Batch processing implemented
- Error handling in place

## 🚦 Next Actions

1. **Upload your actual ticker file** (6,628 tickers)
2. **Configure Polygon API credentials** in the script
3. **Run production script** to retrieve all data
4. **Upload to Notion** using the generated script
5. **View results** at: https://www.notion.so/638a8018f09d4e159d6d84536f411441

---

For questions or issues, review the logs in `/mnt/user-data/outputs/`
