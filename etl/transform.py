"""Data transformation module.
Cleans, normalizes, engineers features, and merges Spotify and Grammys datasets.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Tuple
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)


def clean_text_field(text: any) -> str:
    """Normalize text by converting to lowercase, stripping whitespace,
    removing punctuation and feature tags (e.g. 'feat.', 'remix').
    """
    if pd.isna(text) or not isinstance(text, str):
        return ""
    text = text.lower().strip()
    text = re.sub(r"\(feat[^\)]*\)", "", text)
    text = re.sub(r"\[feat[^\]]*\]", "", text)
    text = re.sub(r"\(remix[^\)]*\)", "", text)
    text = re.sub(r"\(remastered[^\)]*\)", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def extract_artist_from_grammys(row: pd.Series) -> str:
    """Extract lead artist name from Grammys dataset, falling back
    to workers or parenthetical credits when artist is missing.
    """
    if pd.notna(row.get("artist")) and str(row["artist"]).strip():
        return str(row["artist"]).strip()

    workers = str(row.get("workers", "")) if pd.notna(row.get("workers")) else ""
    # Look for parenthetical artist credit, e.g. "..., songwriter (Taylor Swift)"
    matches = re.findall(r"\(([^)]+)\)", workers)
    if matches:
        return matches[-1].strip()

    if "," in workers:
        return workers.split(",")[0].strip()

    return ""


def categorize_grammy_field(category: str) -> str:
    """Map detailed Grammy category into higher-level musical field."""
    cat = str(category).lower()
    if any(k in cat for k in ["record of the year", "album of the year", "song of the year", "new artist"]):
        return "General Field"
    if "pop" in cat:
        return "Pop"
    if any(k in cat for k in ["rock", "metal", "alternative"]):
        return "Rock/Alternative"
    if any(k in cat for k in ["rap", "hip hop", "hip-hop"]):
        return "Rap/Hip-Hop"
    if any(k in cat for k in ["r&b", "rhythm and blues", "urban"]):
        return "R&B"
    if any(k in cat for k in ["country", "americana", "bluegrass"]):
        return "Country/Americana"
    if any(k in cat for k in ["jazz", "blues"]):
        return "Jazz/Blues"
    if any(k in cat for k in ["latin"]):
        return "Latin"
    if any(k in cat for k in ["classical", "orchestral", "opera", "choral"]):
        return "Classical"
    if any(k in cat for k in ["dance", "electronic"]):
        return "Dance/Electronic"
    return "Other / Craft"


def transform_spotify(df: pd.DataFrame) -> pd.DataFrame:
    """Transform and clean Spotify dataset:
    - Removes invalid/corrupt rows (duration_ms <= 0, missing IDs).
    - Deduplicates repeated tracks across genres.
    - Computes duration in minutes, popularity tiers, and audio ratios.
    - Normalizes artist and track strings for deterministic join.
    """
    logger.info(f"Transforming Spotify dataset: initial count = {len(df)}")
    df_clean = df.copy()

    # 1. Filter out corrupt rows detected by quality checks
    df_clean = df_clean[df_clean["duration_ms"] > 0]
    df_clean = df_clean.dropna(subset=["track_id", "track_name", "artists"])

    # 2. Extract primary artist (first artist in multi-artist list)
    df_clean["primary_artist"] = df_clean["artists"].astype(str).apply(
        lambda a: str(a).split(";")[0].strip()
    )

    # 3. Create normalized keys for merging
    df_clean["artist_norm"] = df_clean["primary_artist"].apply(clean_text_field)
    df_clean["track_norm"] = df_clean["track_name"].apply(clean_text_field)

    # 4. Feature engineering
    df_clean["duration_min"] = (df_clean["duration_ms"] / 60000.0).round(2)
    df_clean["popularity_tier"] = pd.cut(
        df_clean["popularity"],
        bins=[-1, 39, 69, 100],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    df_clean["energy_dance_ratio"] = (
        df_clean["energy"] / (df_clean["danceability"] + 0.0001)
    ).round(4)
    df_clean["is_explicit_int"] = df_clean["explicit"].astype(bool).astype(int)

    # 5. Deduplicate tracks appearing across multiple genre playlists
    if "track_genre" in df_clean.columns:
        genres_agg = (
            df_clean.groupby("track_id")["track_genre"]
            .apply(lambda g: ", ".join(sorted(set(g))))
            .rename("all_genres")
        )
        primary_genre = (
            df_clean.groupby("track_id")["track_genre"].first().rename("primary_genre")
        )
        df_dedup = (
            df_clean.drop_duplicates(subset=["track_id"])
            .drop(columns=["track_genre"])
            .merge(genres_agg, on="track_id")
            .merge(primary_genre, on="track_id")
        )
    else:
        df_dedup = df_clean.drop_duplicates(subset=["track_id"])

    logger.info(f"Spotify transformed and deduplicated: {len(df_dedup)} unique tracks.")
    return df_dedup


def transform_grammys(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Transform Grammys dataset:
    - Recovers missing artist names from worker credits.
    - Cleans and normalizes nominee and artist strings.
    - Generates artist-level award profiles and track-level award profiles.

    Returns:
        Tuple of (artist_summary_df, track_summary_df)
    """
    logger.info(f"Transforming Grammys dataset: initial count = {len(df)}")
    df_clean = df.copy()

    # 1. Standardize types
    df_clean["year"] = pd.to_numeric(df_clean["year"], errors="coerce").fillna(0).astype(int)
    df_clean["is_winner"] = df_clean["winner"].astype(bool)

    # 2. Extract and normalize artist & nominee
    df_clean["artist_extracted"] = df_clean.apply(extract_artist_from_grammys, axis=1)
    df_clean["artist_norm"] = df_clean["artist_extracted"].apply(clean_text_field)
    df_clean["nominee_norm"] = df_clean["nominee"].apply(clean_text_field)
    df_clean["grammy_field"] = df_clean["category"].apply(categorize_grammy_field)

    # 3. Build Artist-Level Summary
    artist_summary = (
        df_clean[df_clean["artist_norm"] != ""]
        .groupby("artist_norm")
        .agg(
            grammy_artist_wins=("is_winner", "sum"),
            grammy_artist_nominations=("winner", "count"),
            grammy_artist_first_year=("year", "min"),
            grammy_artist_latest_year=("year", "max"),
        )
        .reset_index()
    )
    artist_summary["has_grammy_winning_artist"] = artist_summary["grammy_artist_wins"] > 0

    # 4. Build Track-Level Summary
    valid_tracks = df_clean[
        (df_clean["artist_norm"] != "") & (df_clean["nominee_norm"] != "")
    ]
    track_summary = (
        valid_tracks.groupby(["artist_norm", "nominee_norm"])
        .agg(
            grammy_track_wins=("is_winner", "sum"),
            grammy_track_nominations=("winner", "count"),
            grammy_track_year=("year", "max"),
            grammy_track_category=("category", "first"),
            grammy_track_field=("grammy_field", "first"),
        )
        .reset_index()
    )
    track_summary["is_grammy_track_winner"] = track_summary["grammy_track_wins"] > 0

    logger.info(
        f"Grammys transformed: {len(artist_summary)} unique artists, {len(track_summary)} unique tracks."
    )
    return artist_summary, track_summary


def merge_datasets(
    df_spotify: pd.DataFrame,
    artist_summary: pd.DataFrame,
    track_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Merge transformed Spotify tracks with Grammy artist and track awards.

    Produces unified dataset where every track contains:
    - Spotify audio features and popularity metrics.
    - Artist award history (wins, nominations, active award years).
    - Track-specific Grammy award metadata (wins, category, year).
    - Consolidated award status tag.
    """
    logger.info("Merging Spotify dataset with Grammys award data...")

    # 1. Merge track-specific Grammy awards
    merged = df_spotify.merge(
        track_summary,
        left_on=["artist_norm", "track_norm"],
        right_on=["artist_norm", "nominee_norm"],
        how="left",
    )

    # 2. Merge artist-level Grammy awards
    merged = merged.merge(artist_summary, on="artist_norm", how="left")

    # 3. Impute defaults for non-award tracks and artists
    merged["grammy_track_wins"] = merged["grammy_track_wins"].fillna(0).astype(int)
    merged["grammy_track_nominations"] = (
        merged["grammy_track_nominations"].fillna(0).astype(int)
    )
    merged["is_grammy_track_winner"] = merged["is_grammy_track_winner"].fillna(False).astype(bool)

    merged["grammy_artist_wins"] = merged["grammy_artist_wins"].fillna(0).astype(int)
    merged["grammy_artist_nominations"] = (
        merged["grammy_artist_nominations"].fillna(0).astype(int)
    )
    merged["has_grammy_winning_artist"] = (
        merged["has_grammy_winning_artist"].fillna(False).astype(bool)
    )

    # 4. Consolidated status column
    def derive_status(row: pd.Series) -> str:
        if row["is_grammy_track_winner"]:
            return "Track Award Winner"
        if row["has_grammy_winning_artist"]:
            return "Artist Award Winner"
        return "Non-Winner"

    merged["award_status"] = merged.apply(derive_status, axis=1)

    # 5. Clean up redundant join keys
    cols_to_drop = [col for col in ["nominee_norm"] if col in merged.columns]
    if cols_to_drop:
        merged = merged.drop(columns=cols_to_drop)

    logger.info(f"Merge completed successfully. Final rows: {len(merged)}, columns: {len(merged.columns)}")
    return merged

