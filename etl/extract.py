"""Data extraction module.
Extracts data from Spotify CSV and Grammys database table.
"""

import logging
import sys
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import pandas as pd
from sqlalchemy import create_engine

# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from etl.config import (
    SPOTIFY_CSV_PATH,
    SOURCE_DB_URI,
    SOURCE_GRAMMYS_TABLE,
)
from etl.validation import validate_spotify_data, validate_grammys_data

logger = logging.getLogger(__name__)


def extract_spotify_csv(
    file_path: Optional[Path] = None, validate: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Extract Spotify dataset from CSV file and run data quality validation.

    Returns:
        Tuple of (DataFrame, quality_report_dict)
    """
    path = Path(file_path or SPOTIFY_CSV_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Spotify dataset CSV not found at: {path}")

    logger.info(f"Extracting Spotify dataset from CSV: {path}")
    # Read CSV (ignoring unnamed row index column if present)
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    logger.info(f"Successfully extracted {len(df)} rows from Spotify CSV.")

    report = {"dataset": "Spotify", "validated": False}
    if validate:
        is_valid, df, report = validate_spotify_data(df, raise_on_error=False)
        report["passed"] = is_valid

    return df, report


def extract_grammys_from_db(
    db_uri: Optional[str] = None,
    table_name: Optional[str] = None,
    validate: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Extract Grammy awards dataset from source SQL database and run data quality validation.

    Returns:
        Tuple of (DataFrame, quality_report_dict)
    """
    uri = db_uri or SOURCE_DB_URI
    table = table_name or SOURCE_GRAMMYS_TABLE

    logger.info(f"Extracting Grammys dataset from DB table '{table}' via {uri}")
    engine = create_engine(uri)
    query = f"SELECT * FROM {table}"
    with engine.connect() as conn:
        df = pd.read_sql_query(query, con=conn)

    logger.info(f"Successfully extracted {len(df)} rows from Grammys database.")

    report = {"dataset": "Grammys", "validated": False}
    if validate:
        is_valid, df, report = validate_grammys_data(df, raise_on_error=False)
        report["passed"] = is_valid

    return df, report


if __name__ == "__main__":
    df_s, rep_s = extract_spotify_csv()
    print("Spotify extraction rows:", len(df_s), "Valid:", rep_s.get("is_valid"))
    df_g, rep_g = extract_grammys_from_db()
    print("Grammys extraction rows:", len(df_g), "Valid:", rep_g.get("is_valid"))
