"""
Backup Archive Extractor Module.
Handles decompressing nested ZIP streams and extracting databases, telemetry logs, and artworks.
Author: Antigravity
Python: 3.13.12
"""

from collections.abc import Generator
import datetime
import io
import json
from pathlib import Path
import sqlite3
from typing import Any
import zipfile


class BackupExtractor:
    """Manages reading and extracting streams from nested application backup archives.

    Why: The application backup is an outer ZIP containing 25 internal ZIP files
    for database storage, history logs, album artworks, and palette tokens.
    """

    def __init__(self, archive_path: Path):
        self.archive_path = Path(archive_path)
        if not self.archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {self.archive_path}")

    def read_tracks_database(self) -> dict[str, dict[str, Any]]:
        """Extracts and parses tracks.db SQLite schema from inside LOCAL_FILES.zip.

        Returns:
            Dictionary mapping track file paths to raw metadata JSON objects.
        """
        tracks_meta: dict[str, dict[str, Any]] = {}
        with zipfile.ZipFile(self.archive_path) as outer_zip:
            local_zip_data = io.BytesIO(outer_zip.read("LOCAL_FILES.zip"))
            with zipfile.ZipFile(local_zip_data) as local_zip:
                tracks_db_bytes = local_zip.read("tracks.db")

        temp_db = self.archive_path.parent / "temp_tracks.db"
        temp_db.write_bytes(tracks_db_bytes)
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            for key, val_json in cursor.execute("SELECT key, value FROM tracks"):
                try:
                    tracks_meta[key] = json.loads(val_json)
                except Exception:
                    continue
            conn.close()
        finally:
            if temp_db.exists():
                temp_db.unlink()
        return tracks_meta

    def read_daily_listen_seconds(self) -> dict[datetime.date, int]:
        """Extracts recorded daily listening seconds from listen_time_daily.db inside LOCAL_FILES.zip.

        Why: Telemetry app records exact playback seconds per calendar day in this SQLite table,
        allowing precise year-filtered listening totals (e.g. 31,411 min in 2026).
        """
        daily_seconds: dict[datetime.date, int] = {}
        try:
            with zipfile.ZipFile(self.archive_path) as outer_zip:
                local_zip_data = io.BytesIO(outer_zip.read("LOCAL_FILES.zip"))
                with zipfile.ZipFile(local_zip_data) as local_zip:
                    if "listen_time_daily.db" not in local_zip.namelist():
                        return daily_seconds
                    db_bytes = local_zip.read("listen_time_daily.db")

            temp_db = self.archive_path.parent / "temp_daily.db"
            temp_db.write_bytes(db_bytes)
            try:
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                for key_str, val_json in cursor.execute("SELECT key, value FROM listen_time_daily"):
                    if key_str.isdigit():
                        date_val = datetime.date(1970, 1, 1) + datetime.timedelta(days=int(key_str))
                        data = json.loads(val_json)
                        daily_seconds[date_val] = data.get("tr", 0)
                conn.close()
            finally:
                if temp_db.exists():
                    temp_db.unlink()
        except Exception:
            pass
        return daily_seconds

    def read_total_listen_minutes(self) -> float | None:
        """Reads recorded total listen minutes from total_listen.txt if available.

        Why: Provides the lifetime accumulated listen counter in seconds under key 'tr'.
        """
        try:
            with zipfile.ZipFile(self.archive_path) as outer_zip:
                local_zip_data = io.BytesIO(outer_zip.read("LOCAL_FILES.zip"))
                with zipfile.ZipFile(local_zip_data) as local_zip:
                    content = local_zip.read("total_listen.txt").decode("utf-8").strip()
                    tl_json = json.loads(content)
                    total_sec = tl_json.get("tr", 0)
                    return total_sec / 60.0
        except Exception:
            return None

    def iterate_history_events(self) -> Generator[dict[str, Any], None, None]:
        """Iterates over all play event log entries inside TEMPDIR_History.zip.

        Yields:
            Parsed event dictionaries representing individual song play sessions.
        """
        with zipfile.ZipFile(self.archive_path) as outer_zip:
            if "TEMPDIR_History.zip" not in outer_zip.namelist():
                return
            hist_zip_data = io.BytesIO(outer_zip.read("TEMPDIR_History.zip"))
            with zipfile.ZipFile(hist_zip_data) as hist_zip:
                for fname in hist_zip.namelist():
                    if not fname.endswith(".json"):
                        continue
                    day_num_str = fname.replace(".json", "")
                    if not day_num_str.isdigit():
                        continue
                    file_date = datetime.date(1970, 1, 1) + datetime.timedelta(days=int(day_num_str))

                    try:
                        raw = hist_zip.read(fname).decode("utf-8")
                        records = json.loads(raw)
                        if isinstance(records, list):
                            for rec in records:
                                rec["_file_date"] = file_date.isoformat()
                                yield rec
                        elif isinstance(records, dict):
                            records["_file_date"] = file_date.isoformat()
                            yield records
                    except Exception:
                        continue

    def extract_artwork(self, track_filename: str, output_path: Path) -> bool:
        """Extracts high-resolution album cover for a specific track from TEMPDIR_Artworks.zip.

        Args:
            track_filename: Exact base name of audio file (e.g. 'Song.flac').
            output_path: Target filesystem path to save PNG.

        Returns:
            True if artwork was found and written; False otherwise.
        """
        png_target = f"{track_filename}.png"
        try:
            with zipfile.ZipFile(self.archive_path) as outer_zip:
                if "TEMPDIR_Artworks.zip" not in outer_zip.namelist():
                    return False
                art_zip_data = io.BytesIO(outer_zip.read("TEMPDIR_Artworks.zip"))
                with zipfile.ZipFile(art_zip_data) as art_zip:
                    if png_target in art_zip.namelist():
                        data = art_zip.read(png_target)
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(data)
                        return True
        except Exception:
            pass
        return False

    def read_palette_colors(self, track_filename: str) -> list[str]:
        """Reads ARGB color swatch array for a specific track from TEMPDIR_Palettes.zip.

        Returns:
            List of CSS hex colors #RRGGBB.
        """
        json_target = f"{track_filename}.json"
        colors: list[str] = []
        try:
            with zipfile.ZipFile(self.archive_path) as outer_zip:
                if "TEMPDIR_Palettes.zip" not in outer_zip.namelist():
                    return colors
                pal_zip_data = io.BytesIO(outer_zip.read("TEMPDIR_Palettes.zip"))
                with zipfile.ZipFile(pal_zip_data) as pal_zip:
                    if json_target in pal_zip.namelist():
                        raw_data = json.loads(pal_zip.read(json_target).decode("utf-8"))
                        int_colors = raw_data.get("colors", [])
                        for val in int_colors:
                            u_val = val & 0xFFFFFFFF
                            r = (u_val >> 16) & 0xFF
                            g = (u_val >> 8) & 0xFF
                            b = u_val & 0xFF
                            colors.append(f"#{r:02x}{g:02x}{b:02x}")
        except Exception:
            pass
        return colors

    def extract_artist_artworks(self, output_dir: Path) -> int:
        """Extracts artist portraits from TEMPDIR_Artworks Artists.zip into output_dir.

        Returns:
            Count of artist image files successfully written.
        """
        count = 0
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(self.archive_path) as outer_zip:
                if "TEMPDIR_Artworks Artists.zip" not in outer_zip.namelist():
                    return 0
                art_data = io.BytesIO(outer_zip.read("TEMPDIR_Artworks Artists.zip"))
                with zipfile.ZipFile(art_data) as artist_zip:
                    for inf in artist_zip.infolist():
                        if inf.file_size > 0:
                            data = artist_zip.read(inf)
                            out_p = output_dir / inf.filename
                            out_p.write_bytes(data)
                            count += 1
        except Exception as e:
            print(f"[Warning] Failed to extract artist artworks: {e}")
        return count
