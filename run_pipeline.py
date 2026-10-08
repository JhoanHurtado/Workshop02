"""Standalone pipeline runner for Workshop-2 ETL.
Executes the tasks in the exact dependency order defined in the Airflow DAG:
1. read_csv
2. transform_csv
3. read_db
4. transform_db
5. merge
6. load
7. store
8. static_report
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["DISABLE_PANDERA_IMPORT_WARNING"] = "True"
os.environ["MPLCONFIGDIR"] = str(PROJECT_ROOT / ".tmp_mpl")

from dags.spotify_grammys_etl_dag import (
    task_read_csv,
    task_transform_csv,
    task_read_db,
    task_transform_db,
    task_merge,
    task_load,
    task_store,
    task_generate_report,
)
from db.init_db import initialize_source_database


def run_full_pipeline():
    """Run all ETL pipeline stages sequentially."""
    print("=" * 70)
    print("STARTING WORKSHOP-2 ETL PIPELINE EXECUTION")
    print("=" * 70)
    start_total = time.time()

    # Pre-step: Ensure initial source database has raw Grammys loaded
    print("\n[Step 0/8] Verifying / Initializing Source Database...")
    initialize_source_database()

    # Step 1: Read CSV
    print("\n[Step 1/8] Running Task: read_csv (Spotify CSV)...")
    t0 = time.time()
    res_read_csv = task_read_csv()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_read_csv}")

    # Step 2: Transform CSV
    print("\n[Step 2/8] Running Task: transform_csv (Pandera validation & clean)...")
    t0 = time.time()
    res_transform_csv = task_transform_csv()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_transform_csv}")

    # Step 3: Read DB
    print("\n[Step 3/8] Running Task: read_db (Grammys DB extraction)...")
    t0 = time.time()
    res_read_db = task_read_db()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_read_db}")

    # Step 4: Transform DB
    print("\n[Step 4/8] Running Task: transform_db (Pandera validation & profiles)...")
    t0 = time.time()
    res_transform_db = task_transform_db()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_transform_db}")

    # Step 5: Merge
    print("\n[Step 5/8] Running Task: merge (Consolidate Spotify & Grammys)...")
    t0 = time.time()
    res_merge = task_merge()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_merge}")

    # Step 6: Load
    print("\n[Step 6/8] Running Task: load (Store merged dataset in warehouse DB)...")
    t0 = time.time()
    res_load = task_load()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_load}")

    # Step 7: Store
    print("\n[Step 7/8] Running Task: store (Export merged dataset to CSV)...")
    t0 = time.time()
    res_store = task_store()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_store}")

    # Step 8: Static Report
    print("\n[Step 8/8] Running Task: static_report (Generate dashboard from DB)...")
    t0 = time.time()
    res_report = task_generate_report()
    print(f" -> Completed in {time.time() - t0:.2f}s: {res_report}")

    total_time = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"WORKSHOP-2 ETL PIPELINE COMPLETED SUCCESSFULLY IN {total_time:.2f}s!")
    print("=" * 70)


if __name__ == "__main__":
    run_full_pipeline()

