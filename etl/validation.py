"""Data quality validation module using Pandera.
Defines schemas and validation routines for extraction and processing phases.
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import pandera.pandas as pa
from pandera import Check, DataFrameSchema, Column

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pandera Schema: Spotify Tracks Dataset
# ---------------------------------------------------------------------------
SpotifyRawSchema = DataFrameSchema(
    columns={
        "track_id": Column(str, nullable=False, title="Spotify Track ID"),
        "artists": Column(str, nullable=True, title="Artist(s)"),
        "album_name": Column(str, nullable=True, title="Album Name"),
        "track_name": Column(str, nullable=True, title="Track Name"),
        "popularity": Column(
            int,
            Check.in_range(0, 100),
            coerce=True,
            title="Track Popularity (0-100)",
        ),
        "duration_ms": Column(
            int,
            Check.greater_than(0),
            coerce=True,
            title="Duration in Milliseconds (>0)",
        ),
        "explicit": Column(bool, coerce=True, title="Explicit Content Flag"),
        "danceability": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Danceability (0.0-1.0)",
        ),
        "energy": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Energy (0.0-1.0)",
        ),
        "key": Column(
            int,
            Check.in_range(-1, 11),
            coerce=True,
            title="Musical Key (-1 to 11)",
        ),
        "loudness": Column(
            float,
            Check.in_range(-60.0, 10.0),
            coerce=True,
            title="Loudness (dB, -60 to 10)",
        ),
        "mode": Column(
            int,
            Check.isin([0, 1]),
            coerce=True,
            title="Mode (0=Minor, 1=Major)",
        ),
        "speechiness": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Speechiness (0.0-1.0)",
        ),
        "acousticness": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Acousticness (0.0-1.0)",
        ),
        "instrumentalness": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Instrumentalness (0.0-1.0)",
        ),
        "liveness": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Liveness (0.0-1.0)",
        ),
        "valence": Column(
            float,
            Check.in_range(0.0, 1.0),
            coerce=True,
            title="Valence / Positivity (0.0-1.0)",
        ),
        "tempo": Column(
            float,
            Check.greater_than_or_equal_to(0.0),
            coerce=True,
            title="Tempo BPM (>=0.0)",
        ),
        "time_signature": Column(
            int,
            Check.in_range(0, 7),
            coerce=True,
            title="Time Signature (0-7)",
        ),
        "track_genre": Column(str, nullable=False, title="Genre Category"),
    },
    coerce=True,
    strict=False,
)


# ---------------------------------------------------------------------------
# Pandera Schema: Grammy Awards Dataset
# ---------------------------------------------------------------------------
GrammysRawSchema = DataFrameSchema(
    columns={
        "year": Column(
            int,
            Check.in_range(1950, 2030),
            coerce=True,
            title="Award Year (1950-2030)",
        ),
        "title": Column(str, nullable=True, title="Ceremony Title"),
        "category": Column(str, nullable=False, title="Award Category"),
        "nominee": Column(str, nullable=True, title="Nominee Work"),
        "artist": Column(str, nullable=True, title="Nominated Artist"),
        "winner": Column(bool, coerce=True, title="Winner Flag"),
    },
    coerce=True,
    strict=False,
)


# ---------------------------------------------------------------------------
# Validation Execution Functions
# ---------------------------------------------------------------------------
def validate_dataset(
    df: pd.DataFrame,
    schema: DataFrameSchema,
    dataset_name: str,
    raise_on_error: bool = False,
) -> Tuple[bool, pd.DataFrame, Dict[str, Any]]:
    """Validate a dataframe against a Pandera schema and generate a quality report."""
    logger.info(f"Starting data quality validation for: {dataset_name} ({len(df)} rows)")
    total_rows = len(df)
    failure_cases_list = []
    is_valid = True

    try:
        validated_df = schema.validate(df, lazy=True)
        logger.info(f"Data quality validation PASSED for: {dataset_name}")
    except pa.errors.SchemaErrors as err:
        is_valid = False
        failure_df = err.failure_cases
        failure_cases_list = failure_df.to_dict(orient="records")
        logger.warning(
            f"Data quality validation FAILED for {dataset_name} with {len(failure_df)} failure cases."
        )
        if raise_on_error:
            raise err
        validated_df = df

    report = {
        "dataset_name": dataset_name,
        "is_valid": is_valid,
        "total_rows": total_rows,
        "failure_count": len(failure_cases_list),
        "sample_failures": failure_cases_list[:10],
    }
    return is_valid, validated_df, report


def validate_spotify_data(
    df: pd.DataFrame, raise_on_error: bool = False
) -> Tuple[bool, pd.DataFrame, Dict[str, Any]]:
    """Validate Spotify dataframe."""
    return validate_dataset(df, SpotifyRawSchema, "Spotify Tracks", raise_on_error)


def validate_grammys_data(
    df: pd.DataFrame, raise_on_error: bool = False
) -> Tuple[bool, pd.DataFrame, Dict[str, Any]]:
    """Validate Grammys dataframe."""
    return validate_dataset(df, GrammysRawSchema, "Grammy Awards", raise_on_error)

