"""
Project Configuration Module for Wrapped Generation.
Centralizes constants, paths, default settings, and dynamic year detection.
Author: Antigravity
Python: 3.13.12
"""

import datetime
from pathlib import Path
import sys

# Ensure UTF-8 output across Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Dynamic target year
CURRENT_YEAR: int = datetime.datetime.now().year

# Project Root Directory
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# Input Archives & Assets
FILES_DIR: Path = ROOT_DIR / "files"


def get_latest_backup_path(files_dir: Path = FILES_DIR) -> Path:
    """Discovers the most recent Namida backup ZIP archive inside the files/ directory.

    Why: Namida produces timestamped ZIP files upon backup (e.g. 'Namida Backup - 2026-11-01 21.58.08.zip').
    Instead of hardcoding a stale filename, dynamically resolves the newest archive by mtime.
    """
    if not files_dir.exists():
        files_dir.mkdir(parents=True, exist_ok=True)

    archives = sorted(
        [p for p in files_dir.glob("*.zip") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if archives:
        return archives[0]
    return files_dir / "Namida Backup.zip"


DEFAULT_BACKUP_PATH: Path = get_latest_backup_path(FILES_DIR)

# Output Root & Organized Subdirectories
OUTPUT_DIR: Path = ROOT_DIR / "output"
DATA_DIR: Path = OUTPUT_DIR / "data"
PANEL_CONFIGS_DIR: Path = DATA_DIR / "panel_configs"
AUDIO_DIR: Path = OUTPUT_DIR / "audio"
TEMP_AUDIO_DIR: Path = AUDIO_DIR / "temp_audio"
SLICES_DIR: Path = OUTPUT_DIR / "slices"
RENDERS_DIR: Path = OUTPUT_DIR / "renders"
ARTWORKS_DIR: Path = OUTPUT_DIR / "artworks"
STORY_DIR: Path = OUTPUT_DIR / "storyboard"
PREVIEW_DIR: Path = OUTPUT_DIR / "previews"
LOGS_DIR: Path = OUTPUT_DIR / "logs"

# Canonical File Paths
DEFAULT_SOUNDTRACK_PATH: Path = AUDIO_DIR / "soundtrack.aac"
STATS_JSON_PATH: Path = DATA_DIR / f"wrapped_stats_{CURRENT_YEAR}.json"
CURATION_JSON_PATH: Path = DATA_DIR / f"user_curation_{CURRENT_YEAR}.json"
LEGACY_STATS_JSON_PATH: Path = DATA_DIR / f"namida_wrapped_{CURRENT_YEAR}.json"
STORY_HTML_PATH: Path = STORY_DIR / "story.html"
ARTWORKS_JSON_PATH: Path = STORY_DIR / "artworks.json"
OUTPUT_VIDEO_PATH: Path = RENDERS_DIR / f"wrapped_{CURRENT_YEAR}.mp4"
CUSTOM_VIDEO_PATH: Path = RENDERS_DIR / "wrapped_custom_export.mp4"
LEGACY_VIDEO_PATH: Path = RENDERS_DIR / f"namida_wrapped_{CURRENT_YEAR}.mp4"
SERVER_LOG_PATH: Path = LOGS_DIR / "studio_server.log"

# Video Specs (10 slides @ 5.0s = 50.0s)
VIDEO_WIDTH: int = 1080
VIDEO_HEIGHT: int = 1920
VIDEO_FPS: int = 25
VIDEO_DURATION_SEC: float = 50.0
TOTAL_FRAMES: int = int(VIDEO_DURATION_SEC * VIDEO_FPS)
CHROME_PATH: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

