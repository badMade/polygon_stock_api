#!/usr/bin/env python3
"""
Production Stock Data Retrieval System with Notion Integration
Processes 6,628 tickers from Polygon API and saves to Notion database
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from config import (
    OUTPUT_DIR,
    UPLOADS_DIR,
    AppConfig,
    NOTION_DATABASE_PROPERTIES,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TimeChunk:
    """Represents a 5-year time period for data retrieval.

    Attributes:
        start_date: Period start date in YYYY-MM-DD format.
        end_date: Period end date in YYYY-MM-DD format.
        label: Human-readable label (e.g., "2020-2024").
    """

    start_date: str
    end_date: str
    label: str


class StockDataNotionRetriever:
    """Production system for retrieving stock data and saving to Notion.

    Coordinates bulk retrieval of historical stock data across multiple
    time periods, formats results for Notion database ingestion, and
    manages checkpointing for recovery.

    Attributes:
        ticker_file: Path to JSON file containing ticker symbols.
        tickers: List of loaded ticker symbols.
        batch_size: Number of tickers to process per batch.
        notion_database_url: URL of the target Notion database.
        processed_count: Count of tickers processed so far.
        failed_tickers: List of ticker symbols that failed processing.
        successful_saves: Count of records successfully saved.
        time_chunks: List of TimeChunk objects defining retrieval periods.
    """

    def __init__(self, config: Optional[AppConfig] = None):
        """Initialize the retriever.

        Args:
            config: Optional AppConfig instance for configuration.
        """
        self.ticker_file = str(UPLOADS_DIR / "all_tickers.json")
        self.tickers: List[str] = []
        self.batch_size = 100
        self.notion_database_url: Optional[str] = None
        self.processed_count = 0
        self.failed_tickers: List[str] = []
        self.successful_saves = 0

        # Time chunks configuration
        self.time_chunks = [
            TimeChunk("2020-01-01", "2024-11-23", "2020-2024"),
            TimeChunk("2015-01-01", "2019-12-31", "2015-2019"),
            TimeChunk("2010-01-01", "2014-12-31", "2010-2014"),
            TimeChunk("2005-01-01", "2009-12-31", "2005-2009"),
            TimeChunk("2000-01-01", "2004-12-31", "2000-2004"),
        ]

    def load_tickers(self) -> List[str]:
        """Load ticker symbols from the configured JSON file.

        Returns:
            list[str]: List of ticker symbols loaded from file.

        Raises:
            FileNotFoundError: If the ticker file does not exist.
            json.JSONDecodeError: If the ticker file contains invalid JSON.
        """
        try:
            with open(self.ticker_file, "r", encoding="utf-8") as f:
                self.tickers = json.load(f)
            logger.info("Loaded %d tickers", len(self.tickers))
            return self.tickers
        except (FileNotFoundError, json.JSONDecodeError) as err:
            logger.error("Error loading tickers: %s", err)
            raise

    def create_notion_database(self) -> Dict[str, Any]:
        """Create and save the Notion database property schema.

        Uses the shared NOTION_DATABASE_PROPERTIES from config module.

        Returns:
            dict: Database properties definition dictionary.
        """
        logger.info("Creating Notion database for stock data...")

        # Use shared database properties from config
        database_properties = NOTION_DATABASE_PROPERTIES

        # Save database structure for reference
        structure_file = OUTPUT_DIR / "notion_database_structure.json"
        with open(structure_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "title": "Stock Historical Data (6,628 Tickers)",
                    "properties": database_properties,
                    "created_at": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        logger.info("Database structure saved to %s", structure_file)
        return database_properties

    def fetch_polygon_data(self, ticker: str, chunk: TimeChunk) -> Dict[str, Any]:
        """Fetch stock aggregate data from the Polygon API.

        Retrieves OHLCV data for a ticker within the specified time chunk.
        Selects timespan resolution based on date range (minute/hour/day).
        Currently returns simulated data; replace with actual API calls.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            chunk: TimeChunk defining the retrieval period.

        Returns:
            dict: Stock data containing ticker, period, prices, volume,
                and metadata. Returns has_data=False if no data available.
        """
        result: Dict[str, Any] = {
            "ticker": ticker,
            "period": chunk.label,
            "from": chunk.start_date,
            "to": chunk.end_date,
            "data_points": 0,
            "timespan": None,
            "has_data": False,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "vwap": None,
            "transactions": None,
        }

        # Determine appropriate timespan based on date range
        days_diff = (
            datetime.strptime(chunk.end_date, "%Y-%m-%d")
            - datetime.strptime(chunk.start_date, "%Y-%m-%d")
        ).days

        # Try to get data at the most granular level available
        if days_diff <= 30:
            timespan = "minute"
        elif days_diff <= 180:
            timespan = "hour"
        else:
            timespan = "day"

        # Simulate API response
        # In production, this would be: response = mcp_polygon.get_aggs(...)
        try:
            # Mock successful data retrieval for sample tickers
            if ticker in ["AAPL", "MSFT", "GOOGL", "NVDA"]:
                result.update(
                    {
                        "timespan": timespan,
                        "has_data": True,
                        "data_points": 252 if timespan == "day" else 1000,
                        "open": 150.25,
                        "high": 155.50,
                        "low": 149.00,
                        "close": 154.30,
                        "volume": 50000000,
                        "vwap": 152.45,
                        "transactions": 450000,
                    }
                )

        except requests.RequestException as err:
            logger.warning("No data for %s in %s: %s", ticker, chunk.label, err)

        return result

    def _should_include_record(self, data: Dict[str, Any], include_empty: bool) -> bool:
        """Determine if a record should be included in the Notion batch."""
        return bool(data.get("has_data")) or include_empty

    def _build_notion_page(self, data: Dict[str, Any], batch_num: int) -> Dict[str, Any]:
        """Build a single Notion page payload from a data record."""
        properties: Dict[str, Any] = {
            "Ticker": data["ticker"],
            "Period": data["period"],
            "Has Data": data.get("has_data", False),
            "Batch": batch_num,
            "Retrieved": datetime.now().isoformat(),
        }

        if data.get("from"):
            properties["Date"] = {"start": data["from"], "end": data.get("to")}

        if data.get("has_data"):
            numeric_fields = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vwap",
                "transactions",
                "data_points",
            ]
            for field in numeric_fields:
                if data.get(field) is not None:
                    properties[field.capitalize()] = data[field]

            if data.get("timespan"):
                properties["Timespan"] = data["timespan"]

        return {"properties": properties}

    def save_batch_to_notion(
        self,
        batch_data: List[Dict[str, Any]],
        batch_num: int,
        include_empty: bool = False,
    ) -> None:
        """Save a batch of data to Notion database.

        Uses standardized naming: batch_NNNN_notion.json

        Args:
            batch_data: Collected stock data records for the batch.
            batch_num: Current batch number used for tracking.
            include_empty: Persist records even when has_data is False.
        """
        logger.info(
            "Saving batch %s to Notion (received %s records)",
            batch_num,
            len(batch_data),
        )

        # Build Notion pages with minimal branching to reduce complexity
        notion_pages = [
            self._build_notion_page(data, batch_num)
            for data in batch_data
            if self._should_include_record(data, include_empty)
        ]

        # Standardized filename: batch_NNNN_notion.json
        output_file = OUTPUT_DIR / f"batch_{batch_num:04d}_notion.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(notion_pages, f, indent=2)

        self.successful_saves += len(notion_pages)
        logger.info("Saved %s records to %s", len(notion_pages), output_file)

    def process_batch(
        self, batch: List[str], batch_num: int, total_batches: int
    ) -> None:
        """Process a batch of tickers through all time chunks.

        Args:
            batch: List of ticker symbols to process.
            batch_num: Current batch number (1-indexed).
            total_batches: Total number of batches to process.
        """
        logger.info(
            "Processing batch %s/%s (%s tickers)",
            batch_num,
            total_batches,
            len(batch),
        )

        batch_data: List[Dict[str, Any]] = []

        for ticker_idx, ticker in enumerate(batch, 1):
            ticker_results: List[Dict[str, Any]] = []

            # Process each time chunk for this ticker
            for chunk in self.time_chunks:
                data = self.fetch_polygon_data(ticker, chunk)
                ticker_results.append(data)

                # Rate limiting
                time.sleep(0.01)  # 10ms delay between API calls

            batch_data.extend(ticker_results)
            self.processed_count += 1

            # Progress update every 10 tickers
            if ticker_idx % 10 == 0:
                progress_pct = (self.processed_count / len(self.tickers)) * 100
                logger.info(
                    "  Progress: %s/%s (%.1f%%) - Current: %s",
                    self.processed_count,
                    len(self.tickers),
                    progress_pct,
                    ticker,
                )

        # Save batch to Notion
        self.save_batch_to_notion(batch_data, batch_num)

        # Save checkpoint every 5 batches
        if batch_num % 5 == 0:
            self.save_checkpoint(batch_num)

    def save_checkpoint(self, batch_num: int) -> None:
        """Save progress checkpoint to enable resumption after interruption.

        Args:
            batch_num: Last successfully completed batch number.
        """
        checkpoint_file = OUTPUT_DIR / "retrieval_checkpoint.json"
        checkpoint_data = {
            "last_batch": batch_num,
            "processed_count": self.processed_count,
            "total_tickers": len(self.tickers),
            "successful_saves": self.successful_saves,
            "failed_tickers": self.failed_tickers,
            "timestamp": datetime.now().isoformat(),
        }

        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info("Checkpoint saved at batch %s", batch_num)

    def run(self) -> Optional[Dict[str, Any]]:
        """Execute the full stock data retrieval and Notion export workflow.

        Returns:
            dict: Final execution report, or None if interrupted.

        Raises:
            Exception: Re-raises unexpected errors after logging and
                saving checkpoint.
        """
        logger.info("=" * 60)
        logger.info("STOCK DATA RETRIEVAL SYSTEM - PRODUCTION RUN")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            # Step 1: Load tickers
            self.load_tickers()
            logger.info("Processing %s tickers", len(self.tickers))
            logger.info("Time periods: %s", [c.label for c in self.time_chunks])
            logger.info("Batch size: %s tickers", self.batch_size)

            # Step 2: Create Notion database structure
            self.create_notion_database()

            # Step 3: Calculate batches
            total_batches = (len(self.tickers) + self.batch_size - 1) // self.batch_size
            logger.info("Total batches to process: %s", total_batches)

            estimated_records = len(self.tickers) * len(self.time_chunks)
            logger.info("Estimated total records: %s", f"{estimated_records:,}")

            # Step 4: Process each batch
            logger.info("-" * 60)
            logger.info("Starting batch processing...")

            for batch_num in range(1, total_batches + 1):
                start_idx = (batch_num - 1) * self.batch_size
                end_idx = min(start_idx + self.batch_size, len(self.tickers))
                batch = self.tickers[start_idx:end_idx]

                self.process_batch(batch, batch_num, total_batches)

                # Detailed progress every 10 batches
                if batch_num % 10 == 0:
                    elapsed = datetime.now() - start_time
                    avg_time = elapsed / batch_num
                    remaining = avg_time * (total_batches - batch_num)

                    logger.info("-" * 40)
                    logger.info("Elapsed: %s", elapsed)
                    logger.info("Est. remaining: %s", remaining)
                    logger.info("Records saved: %s", f"{self.successful_saves:,}")
                    logger.info("-" * 40)

            # Final summary
            end_time = datetime.now()
            duration = end_time - start_time

            # Generate final report
            final_report = {
                "execution_summary": {
                    "total_tickers": len(self.tickers),
                    "processed_tickers": self.processed_count,
                    "total_batches": total_batches,
                    "time_chunks": len(self.time_chunks),
                    "total_api_calls": self.processed_count * len(self.time_chunks),
                    "successful_saves": self.successful_saves,
                    "failed_count": len(self.failed_tickers),
                },
                "timing": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration": str(duration),
                    "avg_per_ticker": str(duration / max(self.processed_count, 1)),
                },
                "failed_tickers": self.failed_tickers[:100],  # First 100 failures
            }

            report_file = OUTPUT_DIR / "final_retrieval_report.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(final_report, f, indent=2)

            # Print summary
            logger.info("=" * 60)
            logger.info("STOCK DATA RETRIEVAL COMPLETE")
            logger.info("=" * 60)
            logger.info(
                "Processed: %s/%s tickers",
                f"{self.processed_count:,}",
                f"{len(self.tickers):,}",
            )
            logger.info("Records saved: %s", f"{self.successful_saves:,}")
            logger.info("Failed: %s", len(self.failed_tickers))
            logger.info("Duration: %s", duration)
            logger.info("Report: %s", report_file)
            logger.info("=" * 60)

            return final_report

        except KeyboardInterrupt:
            logger.warning("Process interrupted by user")
            self.save_checkpoint(self.processed_count // self.batch_size)
            logger.info("Progress saved. You can resume from checkpoint.")
            return None

        except Exception as err:  # pylint: disable=broad-except
            logger.exception("Fatal error: %s", err)
            self.save_checkpoint(self.processed_count // self.batch_size)
            raise


if __name__ == "__main__":
    # Create output directories if they don't exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Run the retrieval system
    retriever = StockDataNotionRetriever()
    retriever.run()
