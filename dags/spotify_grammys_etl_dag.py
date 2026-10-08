"""Airflow DAG: spotify_grammys_etl_dag
Automated ETL pipeline orchestrating extraction from CSV and SQL database,
data quality validation with Pandera, transformations, dataset merging,
loading to warehouse database, CSV storage, and static reporting.
"""

from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import pandas as pd

# Add project root directory to path for Airflow executor
DAGS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DAGS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airflow import DAG
try:
    from airflow.providers.standard.operators.python import PythonOperator
except ImportError:
    from airflow.operators.python import PythonOperator

from etl.config import (
    SPOTIFY_CSV_PATH,
    PROCESSED_DATA_DIR,
    SOURCE_DB_URI,
    SOURCE_GRAMMYS_TABLE,
    WAREHOUSE_DB_URI,
    TARGET_MERGED_TABLE,
    MERGED_CSV_OUTPUT_PATH,
)
from etl.extract import extract_spotify_csv, extract_grammys_from_db
from etl.validation import validate_spotify_data, validate_grammys_data
from etl.transform import (
    transform_spotify,
    transform_grammys,
    merge_datasets,
)
from etl.load import load_to_database, store_to_csv

# Staging intermediate paths for decoupled tasks
STAGING_SPOTIFY_RAW = PROCESSED_DATA_DIR / "staging_spotify_raw.parquet"
STAGING_SPOTIFY_TRANSFORMED = PROCESSED_DATA_DIR / "staging_spotify_transformed.parquet"
STAGING_GRAMMYS_RAW = PROCESSED_DATA_DIR / "staging_grammys_raw.parquet"
STAGING_GRAMMYS_ARTISTS = PROCESSED_DATA_DIR / "staging_grammys_artists.parquet"
STAGING_GRAMMYS_TRACKS = PROCESSED_DATA_DIR / "staging_grammys_tracks.parquet"
STAGING_MERGED = PROCESSED_DATA_DIR / "staging_merged.parquet"


# ---------------------------------------------------------------------------
# Task Functions
# ---------------------------------------------------------------------------
def task_read_csv(**context):
    """Task: Read Spotify dataset from CSV file."""
    print(f"Reading Spotify CSV from: {SPOTIFY_CSV_PATH}")
    df, report = extract_spotify_csv(SPOTIFY_CSV_PATH, validate=False)
    df.to_parquet(STAGING_SPOTIFY_RAW, index=False)
    print(f"Stored {len(df)} raw Spotify records into staging parquet.")
    return {"raw_spotify_rows": len(df)}


def task_transform_csv(**context):
    """Task: Validate with Pandera, clean, and transform Spotify data."""
    print(f"Reading raw Spotify staging data: {STAGING_SPOTIFY_RAW}")
    df = pd.read_parquet(STAGING_SPOTIFY_RAW)

    # 1. Pandera Data Quality Validation
    is_valid, _, report = validate_spotify_data(df, raise_on_error=False)
    print(f"Spotify Pandera Quality Validation Result: Passed={is_valid}")
    if not is_valid:
        print(f"Detected {report['failure_count']} data quality anomalies. Applying cleaning rules.")

    # 2. Transformations and feature engineering
    df_transformed = transform_spotify(df)
    df_transformed.to_parquet(STAGING_SPOTIFY_TRANSFORMED, index=False)
    print(f"Stored {len(df_transformed)} transformed Spotify records to staging.")
    return {"transformed_spotify_rows": len(df_transformed), "dq_passed": is_valid}


def task_read_db(**context):
    """Task: Read Grammy awards dataset from source SQL database."""
    print(f"Reading Grammys from source DB: {SOURCE_DB_URI}")
    df, report = extract_grammys_from_db(SOURCE_DB_URI, SOURCE_GRAMMYS_TABLE, validate=False)
    df.to_parquet(STAGING_GRAMMYS_RAW, index=False)
    print(f"Stored {len(df)} raw Grammy records into staging parquet.")
    return {"raw_grammys_rows": len(df)}


def task_transform_db(**context):
    """Task: Validate with Pandera, clean, and transform Grammys data."""
    print(f"Reading raw Grammys staging data: {STAGING_GRAMMYS_RAW}")
    df = pd.read_parquet(STAGING_GRAMMYS_RAW)

    # 1. Pandera Data Quality Validation
    is_valid, _, report = validate_grammys_data(df, raise_on_error=False)
    print(f"Grammys Pandera Quality Validation Result: Passed={is_valid}")

    # 2. Transformations and feature engineering
    artist_summary, track_summary = transform_grammys(df)
    artist_summary.to_parquet(STAGING_GRAMMYS_ARTISTS, index=False)
    track_summary.to_parquet(STAGING_GRAMMYS_TRACKS, index=False)
    print(
        f"Stored {len(artist_summary)} artist profiles and {len(track_summary)} track profiles."
    )
    return {
        "artist_profiles_count": len(artist_summary),
        "track_profiles_count": len(track_summary),
        "dq_passed": is_valid,
    }


def task_merge(**context):
    """Task: Merge transformed Spotify and Grammy datasets."""
    print("Reading transformed datasets from staging...")
    df_spotify = pd.read_parquet(STAGING_SPOTIFY_TRANSFORMED)
    artist_summary = pd.read_parquet(STAGING_GRAMMYS_ARTISTS)
    track_summary = pd.read_parquet(STAGING_GRAMMYS_TRACKS)

    df_merged = merge_datasets(df_spotify, artist_summary, track_summary)
    df_merged.to_parquet(STAGING_MERGED, index=False)
    print(f"Merged dataset created: {len(df_merged)} rows, {len(df_merged.columns)} columns.")
    return {"merged_rows": len(df_merged)}


def task_load(**context):
    """Task: Load merged dataset into target database table."""
    print(f"Loading merged dataset into warehouse DB: {WAREHOUSE_DB_URI}")
    df_merged = pd.read_parquet(STAGING_MERGED)
    rows_loaded = load_to_database(df_merged, WAREHOUSE_DB_URI, TARGET_MERGED_TABLE)
    print(f"Successfully loaded {rows_loaded} rows into table '{TARGET_MERGED_TABLE}'.")
    return {"rows_loaded": rows_loaded}


def task_store(**context):
    """Task: Store transformed dataset as a CSV file in local storage / Google Drive."""
    print(f"Exporting merged dataset to CSV: {MERGED_CSV_OUTPUT_PATH}")
    df_merged = pd.read_parquet(STAGING_MERGED)
    csv_path = store_to_csv(df_merged, MERGED_CSV_OUTPUT_PATH)
    print(f"CSV export confirmed at: {csv_path}")
    return {"csv_path": str(csv_path)}


def task_generate_report(**context):
    """Task: Generate static visual dashboard and analytical report from database."""
    print(f"Generating static report directly from DB: {WAREHOUSE_DB_URI}")
    from etl.report import generate_full_report

    report_file = generate_full_report()
    print(f"Report generated successfully at: {report_file}")
    return {"report_path": str(report_file)}


# ---------------------------------------------------------------------------
# DAG Definition
# ---------------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="spotify_grammys_etl_dag",
    default_args=default_args,
    description="Automated ETL pipeline: Spotify CSV & Grammys DB to Warehouse & Dashboard",
    schedule=None,  # Manual trigger / On-demand
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "spotify", "grammys", "pandera", "workshop-2"],
) as dag:

    read_csv = PythonOperator(
        task_id="read_csv",
        python_callable=task_read_csv,
    )

    transform_csv = PythonOperator(
        task_id="transform_csv",
        python_callable=task_transform_csv,
    )

    read_db = PythonOperator(
        task_id="read_db",
        python_callable=task_read_db,
    )

    transform_db = PythonOperator(
        task_id="transform_db",
        python_callable=task_transform_db,
    )

    merge = PythonOperator(
        task_id="merge",
        python_callable=task_merge,
    )

    load = PythonOperator(
        task_id="load",
        python_callable=task_load,
    )

    store = PythonOperator(
        task_id="store",
        python_callable=task_store,
    )

    static_report = PythonOperator(
        task_id="static_report",
        python_callable=task_generate_report,
    )

    # -----------------------------------------------------------------------
    # Task Dependencies (Matches Project & Airflow Diagram)
    # -----------------------------------------------------------------------
    read_csv >> transform_csv
    read_db >> transform_db
    [transform_csv, transform_db] >> merge
    merge >> load
    load >> store
    load >> static_report
