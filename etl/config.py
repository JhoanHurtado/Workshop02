"""Configuration module for Workshop-2 ETL Pipeline.
Centralizes paths, database connections, and pipeline parameters.
"""

import os
from pathlib import Path

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Data paths
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

SPOTIFY_CSV_PATH = RAW_DATA_DIR / "spotify_dataset.csv"
GRAMMY_RAW_CSV_PATH = RAW_DATA_DIR / "grammy_awards.csv"
MERGED_CSV_OUTPUT_PATH = PROCESSED_DATA_DIR / "merged_spotify_grammys.csv"

# Database paths and URIs
DB_DIR = BASE_DIR / "db"
SOURCE_DB_PATH = DB_DIR / "source_database.db"
WAREHOUSE_DB_PATH = DB_DIR / "warehouse.db"

# Database connection strings (configurable via environment variables)
SOURCE_DB_URI = os.getenv("SOURCE_DB_URI", f"sqlite:///{SOURCE_DB_PATH}")
WAREHOUSE_DB_URI = os.getenv("WAREHOUSE_DB_URI", f"sqlite:///{WAREHOUSE_DB_PATH}")

# Table names
SOURCE_GRAMMYS_TABLE = "grammy_awards_raw"
TARGET_MERGED_TABLE = "merged_spotify_grammys"
TARGET_ARTISTS_SUMMARY_TABLE = "artist_awards_summary"

# Reports directory
REPORTS_DIR = BASE_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
REPORT_MD_PATH = REPORTS_DIR / "static_dashboard_report.md"

# Ensure runtime directories exist
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, DB_DIR, REPORTS_DIR, FIGURES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

