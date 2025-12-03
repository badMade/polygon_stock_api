"""Configuration module for stock data retrieval system.

Provides centralized configuration, type definitions, and constants
for the stock data retrieval and Notion integration system.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, TypedDict


# =============================================================================
# Path Configuration
# =============================================================================

BASE_DATA_DIR = Path(
    os.getenv("STOCK_APP_DATA_DIR", Path(__file__).resolve().parent / "user-data")
)
OUTPUT_DIR = BASE_DATA_DIR / "outputs"
UPLOADS_DIR = BASE_DATA_DIR / "uploads"


# =============================================================================
# Type Definitions
# =============================================================================


class PeriodDict(TypedDict):
    """Type definition for a time period configuration."""

    from_date: str  # Using from_date to avoid 'from' reserved word
    to_date: str
    label: str


class StockDataDict(TypedDict, total=False):
    """Type definition for stock data returned from API."""

    ticker: str
    period: str
    has_data: bool
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    vwap: Optional[float]
    transactions: Optional[int]
    data_points: int
    timespan: str
    date: Optional[str]


class NotionPageProperties(TypedDict, total=False):
    """Type definition for Notion page properties."""

    Ticker: str
    Period: str
    Has_Data: str  # "__YES__" or "__NO__"
    Batch_Number: int
    Open: Optional[float]
    High: Optional[float]
    Low: Optional[float]
    Close: Optional[float]
    Volume: Optional[int]
    VWAP: Optional[float]
    Transactions: Optional[int]
    Data_Points: int
    Timespan: str


class NotionPage(TypedDict):
    """Type definition for a Notion page."""

    properties: Dict


class BatchData(TypedDict):
    """Type definition for batch file data."""

    data_source_id: str
    batch_number: int
    record_count: int
    timestamp: str
    pages: List[NotionPage]
    ticker_count: Optional[int]


class CheckpointData(TypedDict, total=False):
    """Type definition for checkpoint data."""

    batch: int
    processed: int
    saved: int
    timestamp: str
    failed_tickers: List[str]
    partial: bool
    last_ticker: str


# =============================================================================
# Period Configuration
# =============================================================================


@dataclass
class Period:
    """Represents a time period for data retrieval.

    Attributes:
        from_date: Start date in YYYY-MM-DD format.
        to_date: End date in YYYY-MM-DD format.
        label: Human-readable label (e.g., "2020-2024").
    """

    from_date: str
    to_date: str
    label: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format for backward compatibility."""
        return {
            "from": self.from_date,
            "to": self.to_date,
            "label": self.label,
        }


def get_default_periods() -> List[Period]:
    """Return the default 5-year time periods.

    Returns:
        List of Period objects covering 2000-2024.
    """
    return [
        Period("2020-01-01", "2024-11-23", "2020-2024"),
        Period("2015-01-01", "2019-12-31", "2015-2019"),
        Period("2010-01-01", "2014-12-31", "2010-2014"),
        Period("2005-01-01", "2009-12-31", "2005-2009"),
        Period("2000-01-01", "2004-12-31", "2000-2004"),
    ]


# =============================================================================
# Application Configuration
# =============================================================================


@dataclass
class AppConfig:
    """Application configuration settings.

    Attributes:
        batch_size: Number of tickers to process per batch.
        data_source_id: Notion database data source identifier.
        notion_database_url: URL of the target Notion database.
        ticker_file: Path to JSON file containing ticker symbols.
        periods: List of time periods for data retrieval.
        rate_limit_delay: Delay between API calls in seconds.
        checkpoint_interval: Save checkpoint every N batches.
        batch_file_pattern: Pattern for batch output files.
    """

    batch_size: int = 100
    data_source_id: str = "7c5225aa-429b-4580-946e-ba5b1db2ca6d"
    notion_database_url: str = "https://www.notion.so/638a8018f09d4e159d6d84536f411441"
    ticker_file: str = field(default_factory=lambda: str(UPLOADS_DIR / "all_tickers.json"))
    periods: List[Period] = field(default_factory=get_default_periods)
    rate_limit_delay: float = 0.01  # 10ms between API calls
    checkpoint_interval: int = 10  # Save checkpoint every 10 batches
    batch_file_pattern: str = "batch_{batch_num:04d}_notion.json"

    def get_periods_as_dicts(self) -> List[Dict[str, str]]:
        """Return periods as list of dictionaries for backward compatibility."""
        return [p.to_dict() for p in self.periods]


# =============================================================================
# Constants
# =============================================================================

# Major tickers that receive simulated data in test mode
MAJOR_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

# Notion database properties schema
NOTION_DATABASE_PROPERTIES = {
    "Ticker": {"title": {}},
    "Date": {"date": {}},
    "Period": {
        "select": {
            "options": [
                {"name": "2020-2024", "color": "blue"},
                {"name": "2015-2019", "color": "green"},
                {"name": "2010-2014", "color": "yellow"},
                {"name": "2005-2009", "color": "orange"},
                {"name": "2000-2004", "color": "red"},
            ]
        }
    },
    "Open": {"number": {"format": "number"}},
    "High": {"number": {"format": "number"}},
    "Low": {"number": {"format": "number"}},
    "Close": {"number": {"format": "number"}},
    "Volume": {"number": {"format": "number"}},
    "VWAP": {"number": {"format": "number"}},
    "Transactions": {"number": {"format": "number"}},
    "Has Data": {"checkbox": {}},
    "Data Points": {"number": {"format": "number"}},
    "Timespan": {
        "select": {
            "options": [
                {"name": "minute", "color": "purple"},
                {"name": "hour", "color": "pink"},
                {"name": "day", "color": "gray"},
            ]
        }
    },
    "Retrieved": {"date": {}},
    "Batch": {"number": {"format": "number"}},
}


# Default configuration instance
default_config = AppConfig()
