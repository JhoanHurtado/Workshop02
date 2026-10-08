"""Database initialization script.
Loads the raw Grammys dataset into the initial source SQL database.
"""

import sys
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, inspect

# Add root directory to python path if needed
sys.path.append(str(Path(__file__).resolve().parent.parent))

from etl.config import (
    GRAMMY_RAW_CSV_PATH,
    SOURCE_DB_URI,
    SOURCE_GRAMMYS_TABLE,
)


def initialize_source_database(csv_path: Path = GRAMMY_RAW_CSV_PATH, db_uri: str = SOURCE_DB_URI) -> int:
    """Read raw Grammys CSV and load it into the initial source database."""
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"Raw Grammys CSV not found at {csv_path}")

    print(f"Reading Grammys raw CSV from: {csv_path}")
    df_grammys = pd.read_csv(csv_path)

    # Standardize column types before initial load
    if "year" in df_grammys.columns:
        df_grammys["year"] = pd.to_numeric(df_grammys["year"], errors="coerce").fillna(0).astype(int)
    if "winner" in df_grammys.columns:
        df_grammys["winner"] = df_grammys["winner"].astype(bool)

    engine = create_engine(db_uri)
    with engine.begin() as conn:
        df_grammys.to_sql(
            SOURCE_GRAMMYS_TABLE,
            con=conn,
            if_exists="replace",
            index=False,
        )

    inspector = inspect(engine)
    row_count = len(df_grammys)
    print(f"Successfully loaded {row_count} rows into table '{SOURCE_GRAMMYS_TABLE}' in source DB: {db_uri}")
    return row_count


if __name__ == "__main__":
    count = initialize_source_database()
    print(f"Initialization complete. Total rows in database: {count}")

