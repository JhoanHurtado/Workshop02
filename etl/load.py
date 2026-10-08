"""Data loading module.
Stores transformed dataset into SQL database and exports as CSV (local / Google Drive).
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine

sys.path.append(str(Path(__file__).resolve().parent.parent))

from etl.config import (
    WAREHOUSE_DB_URI,
    TARGET_MERGED_TABLE,
    MERGED_CSV_OUTPUT_PATH,
)

logger = logging.getLogger(__name__)


def load_to_database(
    df: pd.DataFrame,
    db_uri: Optional[str] = None,
    table_name: Optional[str] = None,
    if_exists: str = "replace",
) -> int:
    """Load transformed and merged dataset into target database table."""
    uri = db_uri or WAREHOUSE_DB_URI
    table = table_name or TARGET_MERGED_TABLE

    logger.info(f"Loading {len(df)} rows into target DB table '{table}' via {uri}")
    engine = create_engine(uri)

    with engine.begin() as conn:
        df.to_sql(
            table,
            con=conn,
            if_exists=if_exists,
            index=False,
            chunksize=5000,
        )

    logger.info(f"Successfully loaded {len(df)} rows into database table '{table}'.")
    return len(df)


def store_to_csv(df: pd.DataFrame, output_path: Optional[Path] = None) -> Path:
    """Export transformed and merged dataset as CSV file in local storage."""
    target_path = Path(output_path or MERGED_CSV_OUTPUT_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Storing merged dataset to CSV file at: {target_path}")
    df.to_csv(target_path, index=False)

    size_mb = target_path.stat().st_size / (1024 * 1024)
    logger.info(f"Successfully stored CSV ({len(df)} rows, {size_mb:.2f} MB) at {target_path}")
    return target_path


def export_to_google_drive(
    local_csv_path: Path, gdrive_folder_id: Optional[str] = None
) -> str:
    """Helper function to upload exported CSV to Google Drive.
    Falls back gracefully to local storage if Google API credentials are not provided.
    """
    gdrive_cred_file = os.getenv("GDRIVE_CREDENTIALS_JSON")
    if not gdrive_cred_file or not Path(gdrive_cred_file).exists():
        logger.info(
            "Google Drive API credentials not provided in environment (GDRIVE_CREDENTIALS_JSON). "
            f"Dataset preserved securely in local storage at: {local_csv_path}"
        )
        return str(local_csv_path)

    # In environments with Google Drive credentials configured:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            gdrive_cred_file, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        service = build("drive", "v3", credentials=creds)

        file_metadata = {"name": local_csv_path.name}
        if gdrive_folder_id:
            file_metadata["parents"] = [gdrive_folder_id]

        media = MediaFileUpload(str(local_csv_path), mimetype="text/csv", resumable=True)
        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, webViewLink")
            .execute()
        )
        logger.info(f"Successfully uploaded to Google Drive! File ID: {uploaded.get('id')}")
        return uploaded.get("webViewLink", uploaded.get("id"))
    except Exception as exc:
        logger.warning(f"Google Drive upload encountered an error: {exc}. Using local storage.")
        return str(local_csv_path)

