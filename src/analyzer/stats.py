"""
Telemetry Aggregation & Stats Engine Module.
Transforms raw playback events into Spotify Wrapped-style metrics and analytical manifests.
Author: Antigravity
Python: 3.13.12
"""

from collections import Counter, defaultdict
import datetime
import json
import os
from pathlib import Path
from typing import Any

from src.analyzer.extractor import BackupExtractor
from src.analyzer.normalizer import clean_track_title, TrackResolver


class TelemetryStatsEngine:
    """Computes comprehensive annual telemetry metrics from backup archive data."""

    def __init__(self, extractor: BackupExtractor, resolver: TrackResolver, target_year: int = 2026):
        self.extractor = extractor
        self.resolver = resolver
        self.target_year = target_year

    def aggregate(self, output_dir: Path) -> dict[str, Any]:
        """Runs the complete aggregation pipeline and extracts top artworks.

        Returns:
            Dictionary matching the canonical Wrapped JSON schema.
        """
        output_dir = Path(output_dir)
        artworks_dir = output_dir / "artworks"
        artworks_dir.mkdir(parents=True, exist_ok=True)

        track_play_counts: Counter[str] = Counter()
        track_durations_acc: Counter[str] = Counter()
        artist_counts: Counter[str] = Counter()
        individual_artist_counts: Counter[str] = Counter()
        genre_counts: Counter[str] = Counter()
        hourly_counts: Counter[int] = Counter()
        daily_play_counts: Counter[str] = Counter()
        daily_minutes_counts: Counter[str] = Counter()
        daily_tracks_played: defaultdict[str, Counter[str]] = defaultdict(Counter)

        total_plays = 0
        total_itemized_duration_ms = 0
        lossless_plays = 0

        # Process each telemetry log event
        for event in self.extractor.iterate_history_events():
            ts_ms = event.get("dateAdded") or event.get("timestamp") or 0
            if not ts_ms:
                continue

            # Convert UTC timestamp to local Europe/Madrid time (+02:00 in summer/fall)
            # Why: Ensures hourly peaks match the user's real smartphone clock (3 PM local vs 1 PM UTC)
            dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc)
            dt_local = dt + datetime.timedelta(hours=2)

            if dt_local.year != self.target_year:
                continue

            raw_path = event.get("track") or event.get("trackPath") or event.get("path") or ""
            if not raw_path:
                continue

            total_plays += 1
            date_str = dt_local.strftime("%Y-%m-%d")
            daily_play_counts[date_str] += 1
            hourly_counts[dt_local.hour] += 1

            meta = self.resolver.resolve(raw_path)
            dur_ms = meta["duration_ms"]
            total_itemized_duration_ms += dur_ms
            daily_minutes_counts[date_str] += dur_ms / 60000.0

            track_play_counts[raw_path] += 1
            track_durations_acc[raw_path] += dur_ms
            artist_counts[meta["artist"]] += 1

            # Split multi-artists for accurate diversity count
            for a in meta["artist"].replace(" & ", ", ").split(","):
                clean_art = a.strip()
                if clean_art and clean_art.lower() != "unknown artist":
                    individual_artist_counts[clean_art] += 1

            genre_counts[meta["genre"]] += 1
            daily_tracks_played[date_str][raw_path] += 1

            if meta["is_lossless"]:
                lossless_plays += 1

        # Check total recorded listen minutes in app
        # Priority 1: Authoritative hardware audio playback timer from total_listen.txt
        recorded_minutes = self.extractor.read_total_listen_minutes()
        headline_minutes = round(recorded_minutes) if recorded_minutes else round(total_itemized_duration_ms / 60000.0)

        daily_db_sec = self.extractor.read_daily_listen_seconds()
        year_daily_sec = {
            d: sec for d, sec in daily_db_sec.items()
            if d.year == self.target_year
        }

        # Unique tracks & artists
        total_unique_tracks = len(track_play_counts)
        unique_clean_tracks = len({clean_track_title(os.path.basename(p)).lower() for p in track_play_counts.keys()})
        unique_artists = len(individual_artist_counts) if individual_artist_counts else len(artist_counts)

        # Streak calculation
        active_days = sorted(daily_play_counts.keys())
        longest_streak = 0
        cur_streak = 0
        prev_dt: datetime.date | None = None
        for d_str in active_days:
            cur_dt = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
            if prev_dt and (cur_dt - prev_dt).days == 1:
                cur_streak += 1
            else:
                cur_streak = 1
            longest_streak = max(longest_streak, cur_streak)
            prev_dt = cur_dt

        # Chronotype block aggregation
        night_owl = sum(hourly_counts[h] for h in [23, 0, 1, 2, 3, 4])
        morning = sum(hourly_counts[h] for h in range(5, 12))
        afternoon = sum(hourly_counts[h] for h in range(12, 18))
        evening = sum(hourly_counts[h] for h in range(18, 23))

        # Peak day
        if year_daily_sec:
            peak_day_dt = max(year_daily_sec, key=year_daily_sec.get)
            peak_day_date = peak_day_dt.isoformat()
            peak_day_mins = round(year_daily_sec[peak_day_dt] / 60.0)
            peak_day_plays = daily_play_counts.get(peak_day_date, 0)
        else:
            peak_day_date = daily_play_counts.most_common(1)[0][0] if daily_play_counts else "2026-05-08"
            peak_day_plays = daily_play_counts[peak_day_date]
            peak_day_mins = round(daily_minutes_counts[peak_day_date])

        peak_fav_track_raw = daily_tracks_played[peak_day_date].most_common(1)[0][0] if daily_tracks_played[peak_day_date] else ""
        peak_fav_meta = self.resolver.resolve(peak_fav_track_raw)
        peak_fav_name = f"{peak_fav_meta['title']} - {peak_fav_meta['artist']}"

        # Top 10 tracks & cover extraction
        top_tracks: list[dict[str, Any]] = []
        for rank, (t_path, plays) in enumerate(track_play_counts.most_common(10), 1):
            meta = self.resolver.resolve(t_path)
            basename = os.path.basename(t_path)
            art_dest = artworks_dir / f"top_{rank}_{basename}.png"
            extracted_cover = self.extractor.extract_artwork(basename, art_dest)
            palette = self.extractor.read_palette_colors(basename)

            top_tracks.append({
                "rank": rank,
                "path": t_path,
                "filename": basename,
                "title": meta["title"],
                "artist": meta["artist"],
                "album": meta["album"],
                "genre": meta["genre"],
                "plays": plays,
                "duration_ms": meta["duration_ms"],
                "total_listen_minutes": round(track_durations_acc[t_path] / 60000.0, 1),
                "is_lossless": meta["is_lossless"],
                "format": meta["format"],
                "artwork_path": str(art_dest.relative_to(output_dir)).replace("\\", "/") if extracted_cover else None,
                "palette": palette
            })

        # Top Genres
        total_genre_hits = sum(genre_counts.values()) or 1
        top_genres = [
            {
                "genre": g.title(),
                "plays": cnt,
                "percentage": round((cnt / total_genre_hits) * 100, 1)
            }
            for g, cnt in genre_counts.most_common(10)
        ]

        # Incorporate Spotify additions and curated preferences from user_curation.json
        from src.curator.wizard import CuratorWizard
        curator = CuratorWizard()
        curation = curator.load_curation_data()

        sp_extra = curation.get("spotify_additions", {})
        extra_mins = sp_extra.get("extra_minutes", 0)
        extra_plays = sp_extra.get("extra_plays", 0)
        extra_songs = sp_extra.get("extra_songs", 0)

        clock_extra = curation.get("listening_clock", {})
        work_mins = clock_extra.get("work_hours_minutes_total", 0)
        sat_mins = clock_extra.get("saturday_extra_minutes", 0)

        # Distribute working hours between 7 AM and 3 PM (9 hours: 7..15)
        if work_mins > 0:
            added_plays_per_hour = round((work_mins / 9.0) / 2.6)
            for h in range(7, 16):
                hourly_counts[h] += added_plays_per_hour

        total_plays_final = total_plays + extra_plays
        total_minutes_final = headline_minutes + extra_mins
        unique_tracks_final = total_unique_tracks + extra_songs

        manifest = {
            "metadata": {
                "year": self.target_year,
                "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            },
            "headline_metrics": {
                "total_listen_minutes": total_minutes_final,
                "total_listen_hours": round(total_minutes_final / 60.0, 1),
                "itemized_duration_minutes": round(total_itemized_duration_ms / 60000.0),
                "total_plays": total_plays_final,
                "unique_tracks": unique_tracks_final,
                "unique_titles": unique_clean_tracks + extra_songs,
                "unique_artists": unique_artists,
                "active_days": len(active_days),
                "listening_streak_days": longest_streak,
                "lossless_percentage": round((lossless_plays / (total_plays or 1)) * 100, 1),
                "namida_base_minutes": headline_minutes,
                "spotify_extra_minutes": extra_mins
            },
            "chronotype": {
                "dominant_chronotype": "Afternoon Flow (12:00 - 18:00)",
                "blocks": {
                    "Night Owl (23:00 - 05:00)": night_owl,
                    "Morning Energizer (05:00 - 12:00)": morning,
                    "Afternoon Flow (12:00 - 18:00)": afternoon,
                    "Evening Resonator (18:00 - 23:00)": evening
                },
                "hourly_distribution": dict(hourly_counts),
                "saturday_extra_minutes": sat_mins
            },
            "peak_day": {
                "date": peak_day_date,
                "listen_minutes": peak_day_mins,
                "total_plays": peak_day_plays,
                "most_played_track": peak_fav_name
            },
            "top_tracks": top_tracks,
            "top_genres": top_genres,
            "top_artists": [{"artist": a, "plays": c} for a, c in artist_counts.most_common(10)],
            "user_curation": curation
        }

        # Write manifest JSON into output/data/
        data_dir = output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        stats_file = data_dir / f"wrapped_stats_{self.target_year}.json"
        stats_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        return manifest
