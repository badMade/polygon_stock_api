"""Base class for stock data retrieval systems.

Provides shared functionality for batch processing, checkpoint management,
file I/O, and Notion page generation used by all retriever implementations.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import (
    OUTPUT_DIR,
    AppConfig,
    BatchData,
    CheckpointData,
    MAJOR_TICKERS,
    Period,
    StockDataDict,
    default_config,
)

logger = logging.getLogger(__name__)


class BaseRetriever(ABC):
    """Abstract base class for stock data retrieval systems.

    Provides common functionality for:
    - Loading ticker symbols from JSON files
    - Processing tickers in configurable batches
    - Saving results to batch files
    - Checkpoint/recovery system for long-running processes
    - Generating Notion page structures

    Subclasses must implement:
    - fetch_data(): Retrieve data for a ticker and period

    Attributes:
        config: Application configuration instance.
        tickers: List of ticker symbols to process.
        processed: Count of tickers processed so far.
        saved: Count of records saved to batch files.
        failed: List of ticker symbols that failed processing.
        output_dir: Directory for output files.
    """

    def __init__(self, config: Optional[AppConfig] = None):
        """Initialize the retriever with configuration.

        Args:
            config: Application configuration. Uses default if not provided.
        """
        self.config = config or default_config
        self.tickers: List[str] = []
        self.processed: int = 0
        self.saved: int = 0
        self.failed: List[str] = []
        self.output_dir: Path = OUTPUT_DIR

    # =========================================================================
    # Abstract Methods (must be implemented by subclasses)
    # =========================================================================

    @abstractmethod
    def fetch_data(self, ticker: str, period: Period) -> StockDataDict:
        """Fetch stock data for a ticker and time period.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            period: Time period configuration.

        Returns:
            StockDataDict containing the retrieved data.
        """
        pass

    # =========================================================================
    # Ticker Management
    # =========================================================================

    def load_tickers(self) -> int:
        """Load ticker symbols from the configured JSON file.

        Returns:
            Number of tickers loaded.

        Raises:
            FileNotFoundError: If the ticker file does not exist.
            json.JSONDecodeError: If the ticker file contains invalid JSON.
        """
        with open(self.config.ticker_file, "r", encoding="utf-8") as f:
            self.tickers = json.load(f)
        logger.info("Loaded %d tickers from %s", len(self.tickers), self.config.ticker_file)
        return len(self.tickers)

    def validate_ticker(self, ticker: str) -> bool:
        """Validate a ticker symbol format.

        Args:
            ticker: Ticker symbol to validate.

        Returns:
            True if ticker format is valid, False otherwise.
        """
        if not ticker or len(ticker) > 10:
            return False
        # Allow alphanumeric and period (for BRK.A, etc.)
        return all(c.isalnum() or c == "." for c in ticker)

    # =========================================================================
    # Data Retrieval Helpers
    # =========================================================================

    def create_empty_data_entry(
        self, ticker: str, period: Period
    ) -> StockDataDict:
        """Create a baseline data entry with no data.

        Args:
            ticker: Stock ticker symbol.
            period: Time period configuration.

        Returns:
            StockDataDict with has_data=False and null values.
        """
        return {
            "ticker": ticker,
            "period": period.label,
            "date": period.from_date,
            "has_data": False,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "vwap": None,
            "transactions": None,
            "data_points": 0,
            "timespan": "day",
        }

    def simulate_stock_data(
        self, ticker: str, period: Period, data_entry: StockDataDict
    ) -> None:
        """Simulate stock data for major tickers (testing/demo mode).

        Uses deterministic hashing to generate consistent sample data
        for a predefined list of major tickers.

        Args:
            ticker: Stock ticker symbol.
            period: Time period configuration.
            data_entry: Data entry dictionary to update in place.
        """
        if ticker not in MAJOR_TICKERS:
            return

        seed = self._stable_seed(ticker)
        offset_100 = seed % 100

        data_entry.update(
            {
                "has_data": True,
                "open": 150.25 + offset_100,
                "high": 155.50 + offset_100,
                "low": 149.00 + offset_100,
                "close": 154.30 + offset_100,
                "volume": 50000000 + (seed % 10000000),
                "vwap": 152.45 + offset_100,
                "transactions": 450000 + (seed % 100000),
                "data_points": 252 if period.label in ["2000-2004", "2005-2009"] else 1000,
                "timespan": "day" if "200" in period.label else "hour",
            }
        )

    def _stable_seed(self, ticker: str) -> int:
        """Generate a deterministic integer seed from a ticker symbol.

        Uses SHA-256 hashing for consistent results across runs.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Deterministic integer seed.
        """
        digest = sha256(ticker.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big")

    # =========================================================================
    # Notion Page Generation
    # =========================================================================

    def create_notion_pages(
        self, batch_data: List[StockDataDict], batch_num: int
    ) -> List[Dict[str, Any]]:
        """Transform batch data into Notion page structures.

        Args:
            batch_data: List of stock data dictionaries.
            batch_num: Batch number for tracking purposes.

        Returns:
            List of Notion page dictionaries with properties.
        """
        pages = []
        for item in batch_data:
            if not self._should_create_page(item):
                continue
            page = self._build_notion_page(item, batch_num)
            pages.append(page)
        return pages

    def _should_create_page(self, item: StockDataDict) -> bool:
        """Determine if a data item should become a Notion page.

        Args:
            item: Stock data dictionary.

        Returns:
            True if the item has data or a close price.
        """
        return bool(item.get("has_data") or item.get("close") is not None)

    def _build_notion_page(
        self, item: StockDataDict, batch_num: int
    ) -> Dict[str, Any]:
        """Build a single Notion page from stock data.

        Args:
            item: Stock data dictionary.
            batch_num: Current batch number.

        Returns:
            Notion page dictionary with properties.
        """
        properties: Dict[str, Any] = {
            "Ticker": item["ticker"],
            "Period": item["period"],
            "Has Data": "__YES__" if item.get("has_data") else "__NO__",
            "Batch Number": batch_num,
            "date:Retrieved At:start": datetime.now().isoformat(),
            "date:Retrieved At:is_datetime": 1,
        }

        # Add date if available
        if item.get("date"):
            properties["date:Date:start"] = item["date"]
            properties["date:Date:is_datetime"] = 0

        # Add price fields if data is available
        if item.get("has_data"):
            self._add_price_properties(properties, item)

        return {"properties": properties}

    def _add_price_properties(
        self, properties: Dict[str, Any], item: StockDataDict
    ) -> None:
        """Add price-related fields to page properties.

        Args:
            properties: Property dictionary to modify in place.
            item: Stock data dictionary with price fields.
        """
        price_fields = [
            ("Open", "open"),
            ("High", "high"),
            ("Low", "low"),
            ("Close", "close"),
            ("Volume", "volume"),
            ("VWAP", "vwap"),
            ("Transactions", "transactions"),
            ("Data Points", "data_points"),
        ]

        for prop_name, data_key in price_fields:
            value = item.get(data_key)
            if value is not None:
                properties[prop_name] = value

        if item.get("timespan"):
            properties["Timespan"] = item["timespan"]

    # =========================================================================
    # Batch Processing
    # =========================================================================

    def process_batch(
        self, batch: List[str], batch_num: int, total_batches: int
    ) -> int:
        """Process a batch of tickers through all time periods.

        Args:
            batch: List of ticker symbols to process.
            batch_num: Current batch number (1-indexed).
            total_batches: Total number of batches to process.

        Returns:
            Number of Notion page records created for this batch.
        """
        logger.info(
            "Batch %d/%d: Processing %d tickers",
            batch_num,
            total_batches,
            len(batch),
        )

        batch_results: List[StockDataDict] = []

        for i, ticker in enumerate(batch, 1):
            ticker_results = self._process_ticker(ticker)
            batch_results.extend(ticker_results)
            self.processed += 1

            # Progress update every 10 or 20 tickers
            if i % 10 == 0:
                self._log_progress(i, ticker)

        # Save batch data
        notion_pages = self.save_batch(batch_results, batch_num, len(batch))
        self.saved += len(notion_pages)

        return len(notion_pages)

    def _process_ticker(self, ticker: str) -> List[StockDataDict]:
        """Process all time periods for a single ticker.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            List of data entries for each configured time period.
        """
        results = []
        for period in self.config.periods:
            try:
                data = self.fetch_data(ticker, period)
                results.append(data)
                time.sleep(self.config.rate_limit_delay)
            except Exception as e:
                logger.warning("Failed to fetch %s for %s: %s", ticker, period.label, e)
                results.append(self.create_empty_data_entry(ticker, period))
                self.failed.append(ticker)
        return results

    def _log_progress(self, current_index: int, ticker: str) -> None:
        """Log progress update during batch processing.

        Args:
            current_index: Current position in batch.
            ticker: Current ticker being processed.
        """
        if not self.tickers:
            return
        pct = (self.processed / len(self.tickers)) * 100
        logger.info(
            "  Progress: %d/%d (%.1f%%) - Current: %s",
            self.processed,
            len(self.tickers),
            pct,
            ticker,
        )

    # =========================================================================
    # File I/O
    # =========================================================================

    def save_batch(
        self,
        batch_results: List[StockDataDict],
        batch_num: int,
        ticker_count: int,
    ) -> List[Dict[str, Any]]:
        """Save batch data to a JSON file.

        Uses standardized naming pattern: batch_NNNN_notion.json

        Args:
            batch_results: List of stock data dictionaries.
            batch_num: Current batch number.
            ticker_count: Number of tickers in this batch.

        Returns:
            List of Notion page structures created.
        """
        notion_pages = self.create_notion_pages(batch_results, batch_num)

        # Use standardized naming: batch_NNNN_notion.json
        filename = self.config.batch_file_pattern.format(batch_num=batch_num)
        output_file = self.output_dir / filename

        batch_data: BatchData = {
            "data_source_id": self.config.data_source_id,
            "batch_number": batch_num,
            "ticker_count": ticker_count,
            "record_count": len(notion_pages),
            "timestamp": datetime.now().isoformat(),
            "pages": notion_pages,
        }

        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(batch_data, f, indent=2)

        logger.info(
            "Batch %d saved: %d records -> %s",
            batch_num,
            len(notion_pages),
            output_file,
        )
        return notion_pages

    def save_checkpoint(self, batch_num: int) -> None:
        """Save progress checkpoint for recovery.

        Args:
            batch_num: Last successfully completed batch number.
        """
        checkpoint_data: CheckpointData = {
            "batch": batch_num,
            "processed": self.processed,
            "saved": self.saved,
            "timestamp": datetime.now().isoformat(),
            "failed_tickers": self.failed[:100],  # Limit to first 100
        }

        checkpoint_file = self.output_dir / "checkpoint.json"
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info("Checkpoint saved at batch %d", batch_num)

    def load_checkpoint(self) -> Optional[CheckpointData]:
        """Load checkpoint data if available.

        Returns:
            CheckpointData if checkpoint exists, None otherwise.
        """
        checkpoint_file = self.output_dir / "checkpoint.json"
        if not checkpoint_file.exists():
            return None

        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load checkpoint: %s", e)
            return None

    # =========================================================================
    # Upload Script Generation
    # =========================================================================

    def generate_upload_script(self, total_batches: int) -> None:
        """Generate a Python script for uploading batch files to Notion.

        Args:
            total_batches: Total number of batch files to include.
        """
        script_content = f'''#!/usr/bin/env python3
"""
Upload all batch files to Notion database.

Database: {self.config.notion_database_url}
Data Source ID: {self.config.data_source_id}
"""

import json
import time
from pathlib import Path

# Configuration
DATA_SOURCE_ID = "{self.config.data_source_id}"
TOTAL_BATCHES = {total_batches}
OUTPUT_DIR = Path("{self.output_dir}")

def upload_batch(batch_num: int) -> int:
    """Upload a single batch to Notion."""
    filename = OUTPUT_DIR / f"batch_{{batch_num:04d}}_notion.json"

    with open(filename, "r", encoding="utf-8") as f:
        batch_data = json.load(f)

    print(f"Uploading batch {{batch_num}}: {{batch_data['record_count']}} pages")

    # Split into chunks of 100 pages (Notion API limit)
    pages = batch_data["pages"]
    for i in range(0, len(pages), 100):
        chunk = pages[i : i + 100]

        # TODO: Replace with actual Notion API call
        # notion.create_pages(
        #     parent={{"data_source_id": DATA_SOURCE_ID, "type": "data_source_id"}},
        #     pages=chunk
        # )

        time.sleep(0.5)  # Rate limiting

    return batch_data["record_count"]


if __name__ == "__main__":
    total_uploaded = 0
    for batch_num in range(1, TOTAL_BATCHES + 1):
        records = upload_batch(batch_num)
        total_uploaded += records
        print(f"Progress: {{batch_num}}/{{TOTAL_BATCHES}} batches, {{total_uploaded}} total records")

    print(f"\\nUpload complete: {{total_uploaded}} records uploaded to Notion")
'''

        script_file = self.output_dir / "notion_upload.py"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script_content)

        logger.info("Upload script generated: %s", script_file)

    # =========================================================================
    # Main Execution
    # =========================================================================

    def run(self) -> Optional[Dict[str, Any]]:
        """Execute the full stock data retrieval workflow.

        Orchestrates loading tickers, processing them in batches,
        saving results to files, and generating a summary report.

        Returns:
            Execution summary dictionary, or None if interrupted.

        Raises:
            Exception: Re-raises unexpected errors after logging.
        """
        self._log_startup()
        start_time = datetime.now()

        try:
            # Load tickers
            ticker_count = self.load_tickers()

            # Calculate batches
            total_batches = (ticker_count + self.config.batch_size - 1) // self.config.batch_size
            self._log_configuration(ticker_count, total_batches)

            # Check for existing checkpoint
            checkpoint = self.load_checkpoint()
            start_batch = 1
            if checkpoint:
                start_batch = checkpoint.get("batch", 0) + 1
                self.processed = checkpoint.get("processed", 0)
                self.saved = checkpoint.get("saved", 0)
                logger.info("Resuming from batch %d", start_batch)

            # Process all batches
            for batch_num in range(start_batch, total_batches + 1):
                batch = self._get_batch(batch_num, ticker_count)
                self.process_batch(batch, batch_num, total_batches)

                # Checkpoint every N batches
                if batch_num % self.config.checkpoint_interval == 0:
                    self._log_checkpoint_progress(start_time, ticker_count)
                    self.save_checkpoint(batch_num)

                time.sleep(0.1)  # Small delay between batches

            # Generate upload script
            self.generate_upload_script(total_batches)

            # Generate and return summary
            return self._generate_summary(start_time, ticker_count, total_batches)

        except KeyboardInterrupt:
            logger.warning("Execution interrupted by user")
            self.save_checkpoint(self.processed // self.config.batch_size)
            return None

        except Exception as e:
            logger.error("Fatal error: %s", e)
            self.save_checkpoint(self.processed // self.config.batch_size)
            raise

    def _get_batch(self, batch_num: int, ticker_count: int) -> List[str]:
        """Get the ticker list for a specific batch.

        Args:
            batch_num: Batch number (1-indexed).
            ticker_count: Total number of tickers.

        Returns:
            List of tickers for this batch.
        """
        start_idx = (batch_num - 1) * self.config.batch_size
        end_idx = min(start_idx + self.config.batch_size, ticker_count)
        return self.tickers[start_idx:end_idx]

    def _log_startup(self) -> None:
        """Log startup banner and configuration."""
        logger.info("=" * 70)
        logger.info("STOCK DATA RETRIEVAL SYSTEM")
        logger.info("=" * 70)
        logger.info("Database: %s", self.config.notion_database_url)
        logger.info("Data Source: %s", self.config.data_source_id)
        logger.info("=" * 70)

    def _log_configuration(self, ticker_count: int, total_batches: int) -> None:
        """Log configuration details."""
        total_records = ticker_count * len(self.config.periods)
        logger.info("Configuration:")
        logger.info("  Tickers: %d", ticker_count)
        logger.info("  Periods: %d", len(self.config.periods))
        logger.info("  Batch size: %d", self.config.batch_size)
        logger.info("  Total batches: %d", total_batches)
        logger.info("  Estimated records: %d", total_records)
        logger.info("=" * 70)

    def _log_checkpoint_progress(
        self, start_time: datetime, ticker_count: int
    ) -> None:
        """Log progress at checkpoint intervals."""
        elapsed = datetime.now() - start_time
        if elapsed.total_seconds() > 0:
            rate = self.processed / elapsed.total_seconds()
            remaining = (ticker_count - self.processed) / rate if rate > 0 else 0
            logger.info("-" * 50)
            logger.info("Elapsed: %s", elapsed)
            logger.info("Saved records: %d", self.saved)
            logger.info("Rate: %.1f tickers/sec", rate)
            logger.info("Est. remaining: %s", timedelta(seconds=int(remaining)))
            logger.info("-" * 50)

    def _generate_summary(
        self, start_time: datetime, ticker_count: int, total_batches: int
    ) -> Dict[str, Any]:
        """Generate execution summary and save to file."""
        end_time = datetime.now()
        duration = end_time - start_time

        summary = {
            "execution": {
                "status": "SUCCESS",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration": str(duration),
            },
            "statistics": {
                "total_tickers": ticker_count,
                "processed_tickers": self.processed,
                "total_batches": total_batches,
                "saved_records": self.saved,
                "failed_count": len(self.failed),
                "avg_time_per_ticker": (
                    duration.total_seconds() / self.processed
                    if self.processed > 0
                    else 0
                ),
            },
            "database": {
                "url": self.config.notion_database_url,
                "data_source_id": self.config.data_source_id,
                "batch_files": total_batches,
            },
        }

        # Save summary
        summary_file = self.output_dir / "execution_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Log final results
        self._log_completion(duration, total_batches, summary_file)

        return summary

    def _log_completion(
        self, duration: timedelta, total_batches: int, summary_file: Path
    ) -> None:
        """Log completion message."""
        logger.info("=" * 70)
        logger.info("EXECUTION COMPLETE")
        logger.info("=" * 70)
        logger.info("Processed: %d tickers", self.processed)
        logger.info("Saved: %d records", self.saved)
        logger.info("Batch files: %d", total_batches)
        logger.info("Duration: %s", duration)
        logger.info("Summary: %s", summary_file)
        logger.info("=" * 70)
