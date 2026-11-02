"""
Automated Data Synchronization Module for Namida Backups.
Monitors the files/ directory, detects the latest backup ZIP archive by timestamp,
and ensures telemetry manifests and storyboard DOM are automatically synchronized upon launch.
Author: Antigravity
Python: 3.13.12
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional

from src.analyzer.extractor import BackupExtractor
from src.analyzer.normalizer import TrackResolver
from src.analyzer.stats import TelemetryStatsEngine
from src.config import (
    CURRENT_YEAR,
    FILES_DIR,
    OUTPUT_DIR,
    STATS_JSON_PATH,
    get_latest_backup_path,
)
from src.templates.builder import StoryboardBuilder

logger = logging.getLogger("namida.sync")


def sync_backup_data(
    archive_path: Optional[Path] = None,
    target_year: int = CURRENT_YEAR,
    force: bool = False,
    recompile_storyboard: bool = True,
) -> tuple[bool, str]:
    """Inspects the files/ directory and synchronizes telemetry data from the latest backup archive.

    Why: The user updates their listening data by placing newly exported Namida backup ZIPs
    into files/. This function guarantees that the pipeline and Web Studio always operate
    on the freshest backup data automatically upon launch, without requiring manual CLI steps.

    Args:
        archive_path: Explicit path to a backup ZIP, or None to auto-resolve the newest in files/.
        target_year: Analysis year (defaults to current calendar year).
        force: If True, re-aggregates even if stats manifest is newer than archive.
        recompile_storyboard: If True, recompiles story.html immediately upon successful sync.

    Returns:
        tuple[bool, str]: (was_synchronized, status_message)
    """
    resolved_archive = archive_path or get_latest_backup_path(FILES_DIR)

    if not resolved_archive or not resolved_archive.exists() or not resolved_archive.is_file():
        msg = f"No backup archive found in '{FILES_DIR}'. Please place your Namida backup ZIP in 'files/'."
        logger.warning(msg)
        return False, msg

    # Check whether synchronization is required
    stats_file = STATS_JSON_PATH
    sync_needed = force or not stats_file.exists()

    if not sync_needed and stats_file.exists():
        archive_mtime = resolved_archive.stat().st_mtime
        stats_mtime = stats_file.stat().st_mtime
        if archive_mtime > stats_mtime:
            sync_needed = True

    if not sync_needed:
        msg = f"Data is already up to date with '{resolved_archive.name}'."
        logger.info(msg)
        print(f"[DATA SYNC] {msg}")
        return False, msg

    archive_dt = datetime.fromtimestamp(resolved_archive.stat().st_mtime, tz=timezone.utc)
    print(f"\n[DATA SYNC] Synchronizing latest backup: {resolved_archive.name} ({archive_dt.strftime('%Y-%m-%d %H:%M:%S UTC')})")

    try:
        extractor = BackupExtractor(resolved_archive)
        raw_tracks = extractor.read_tracks_database()
        resolver = TrackResolver(raw_tracks)
        engine = TelemetryStatsEngine(extractor, resolver, target_year=target_year)
        manifest = engine.aggregate(OUTPUT_DIR)

        headline = manifest.get("headline_metrics", {})
        total_mins = headline.get("total_listen_minutes", 0)
        total_plays = headline.get("total_plays", 0)
        unique_tracks = headline.get("unique_tracks", 0)

        success_msg = (
            f"Successfully synchronized '{resolved_archive.name}' "
            f"({total_mins:,} mins, {total_plays:,} plays, {unique_tracks:,} tracks)."
        )
        print(f"[DATA SYNC] {success_msg}")

        if recompile_storyboard:
            builder = StoryboardBuilder(target_year=target_year)
            builder.build()
            print("[DATA SYNC] HTML5 Storyboard recompiled with fresh telemetry.")

        return True, success_msg
    except Exception as exc:
        err_msg = f"Failed to synchronize backup '{resolved_archive.name}': {exc}"
        logger.exception(err_msg)
        print(f"[DATA SYNC ERROR] {err_msg}")
        return False, err_msg
