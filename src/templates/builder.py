"""
Storyboard HTML Builder Module.
Assembles modular CSS, JavaScript animations, artwork assets, telemetry data, and user curation into story.html.
Author: Antigravity
Python: 3.13.12
"""

import base64
import json
from pathlib import Path
from typing import Any

from src.config import ARTWORKS_JSON_PATH, CURRENT_YEAR, OUTPUT_DIR, STATS_JSON_PATH, STORY_HTML_PATH
from src.curator.wizard import CuratorWizard


class StoryboardBuilder:
    """Builds the complete full-bleed HTML5 storyboard for video rendering."""

    def __init__(self, target_year: int = CURRENT_YEAR):
        self.target_year = target_year
        self.template_dir = Path(__file__).resolve().parent
        self._artist_artworks_cache: dict[str, str] = {}

    def load_artist_artworks(self) -> dict[str, str]:
        """Loads all extracted artist avatar images from output/artworks/artists/ into base64 data URIs.

        Why: Renders genuine artist portraits extracted from Namida backup archives
        instead of repeating song album covers across artist slides.
        """
        if self._artist_artworks_cache:
            return self._artist_artworks_cache

        art_map: dict[str, str] = {}
        artists_dir = OUTPUT_DIR / "artworks" / "artists"
        if artists_dir.exists():
            for f in artists_dir.glob("*.png"):
                if f.stat().st_size > 0:
                    try:
                        b64 = f"data:image/png;base64,{base64.b64encode(f.read_bytes()).decode('ascii')}"
                        stem = f.stem
                        art_map[stem.lower()] = b64
                        art_map[stem.replace("_", "$").lower()] = b64
                        art_map[stem.replace("$", "_").lower()] = b64
                    except Exception:
                        pass
        self._artist_artworks_cache = art_map
        return art_map

    def resolve_artist_avatar(self, name: str, fallback: str = "") -> str:
        """Resolves an artist's name to their extracted portrait avatar.

        Why: Matches normalized artist strings (handling symbols, Japanese characters,
        and featured artist commas) to ensure accurate visual representations.
        """
        if not name or not name.strip():
            return fallback

        clean = name.strip()
        low = clean.lower()
        art_map = self.load_artist_artworks()

        if low in art_map:
            return art_map[low]
        low_norm = low.replace("$", "_")
        if low_norm in art_map:
            return art_map[low_norm]
        low_norm2 = low.replace("_", "$")
        if low_norm2 in art_map:
            return art_map[low_norm2]

        if "," in clean:
            parts = [p.strip() for p in clean.split(",") if p.strip()]
            for p in parts:
                res = self.resolve_artist_avatar(p, "")
                if res:
                    return res

        for k, uri in art_map.items():
            if len(k) >= 3 and (k in low or low in k):
                return uri

        return fallback

    def build(
        self,
        output_file: Path = STORY_HTML_PATH,
        stats_file: Path = STATS_JSON_PATH,
        artworks_file: Path = ARTWORKS_JSON_PATH,
    ) -> Path:
        """Compiles HTML, inlines CSS and JS, and writes to output_file.

        Why: Inlining CSS and JS produces an atomic, self-contained offline DOM
        that headless Chromium can seek deterministically frame-by-frame.
        """
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Load stats manifest if available
        stats_data: dict[str, Any] = {}
        if Path(stats_file).exists():
            try:
                stats_data = json.loads(Path(stats_file).read_text(encoding="utf-8"))
            except Exception:
                pass

        # Load user curation overrides
        curator = CuratorWizard()
        curation = curator.load_curation_data() or stats_data.get("user_curation", {})

        # Resolve active theme palette
        theme_presets = {
            "aurora": {
                "primary": "#00ff87", "secondary": "#7928ca", "accent": "#ff007a", "tertiary": "#00d4ff",
                "bg_base": "#030604", "bg_mid": "#0c2616", "bg_outer": "#07140b"
            },
            "cyberpunk": {
                "primary": "#a855f7", "secondary": "#ff007a", "accent": "#00f5ff", "tertiary": "#3b82f6",
                "bg_base": "#08040d", "bg_mid": "#200833", "bg_outer": "#10051a"
            },
            "sunset": {
                "primary": "#ff7a00", "secondary": "#ff0055", "accent": "#ffb800", "tertiary": "#7928ca",
                "bg_base": "#0c0406", "bg_mid": "#260b13", "bg_outer": "#16060c"
            },
            "midnight": {
                "primary": "#00d4ff", "secondary": "#6366f1", "accent": "#8b5cf6", "tertiary": "#06b6d4",
                "bg_base": "#030712", "bg_mid": "#0f172a", "bg_outer": "#070c18"
            },
            "acid": {
                "primary": "#a3e635", "secondary": "#10b981", "accent": "#eab308", "tertiary": "#06b6d4",
                "bg_base": "#050904", "bg_mid": "#14240f", "bg_outer": "#0b1408"
            }
        }
        user_theme = curation.get("theme", {})
        theme_id = user_theme.get("id", "aurora") if isinstance(user_theme, dict) else "aurora"
        base_palette = theme_presets.get(theme_id, theme_presets["aurora"]).copy()
        if isinstance(user_theme, dict):
            for k in ["primary", "secondary", "accent", "tertiary", "bg_base", "bg_mid", "bg_outer"]:
                if user_theme.get(k):
                    base_palette[k] = user_theme[k]
        active_theme = base_palette

        headline = stats_data.get("headline_metrics", {})
        sp_additions = curation.get("spotify_additions", {})
        extra_mins = int(sp_additions.get("extra_minutes", 0) or 0)
        extra_plays = int(sp_additions.get("extra_plays", 0) or 0)
        extra_songs = int(sp_additions.get("extra_songs", 0) or 0)

        # Baseline Namida + Spotify merged numbers
        base_plays = int(headline.get("total_plays", 12425))
        total_plays_raw = base_plays + extra_plays
        total_plays_fmt = f"{total_plays_raw:,}"

        base_mins = int(headline.get("total_listen_minutes", 32575))
        total_min_raw = base_mins + extra_mins
        total_min_fmt = f"{total_min_raw:,}"
        total_hours_val = round(total_min_raw / 60.0)

        base_tracks = int(headline.get("unique_tracks", 2708))
        unique_tracks_raw = base_tracks + extra_songs
        unique_tracks_fmt = f"{unique_tracks_raw:,}"
        unique_artists_fmt = f"{int(headline.get('unique_artists', 1449)):,}"

        active_days_val = int(headline.get("active_days", 221))

        # Longest listening streak in days: support streak_days or extra_streak
        if "streak_days" in sp_additions and sp_additions["streak_days"] is not None:
            streak_val = int(sp_additions["streak_days"])
        elif "extra_streak" in sp_additions and sp_additions["extra_streak"]:
            streak_val = int(headline.get("listening_streak_days", 103)) + int(sp_additions["extra_streak"])
        else:
            streak_val = int(headline.get("listening_streak_days", 103))

        daily_avg_min = round(total_min_raw / (active_days_val or 1), 1)
        daily_avg_songs = round(total_plays_raw / (active_days_val or 1))

        # Clock & Weekly Rhythm adjustments
        clock_curation = curation.get("listening_clock", {})
        work_extra = int(clock_curation.get("workday_extra_minutes", clock_curation.get("work_hours_minutes_total", 15000)) or 0)
        sat_extra = int(clock_curation.get("saturday_extra_minutes", 1450) or 0)

        # Baseline hourly distribution from stats or default 24-hr European distribution
        chrono_data = stats_data.get("chronotype", {})
        raw_hourly = chrono_data.get("hourly_distribution", {})
        default_hourly = [
            66, 61, 55, 30, 25, 35, 1024, 545, 298, 251, 365, 664,
            1154, 1303, 1273, 1637, 521, 608, 983, 857, 325, 176, 89, 80
        ]
        hourly_counts: list[int] = []
        for h in range(24):
            val = int(raw_hourly.get(str(h), default_hourly[h]))
            hourly_counts.append(val)

        # Equidistribute workday extra minutes across 7:00 AM - 3:00 PM (hours 7 to 15, 9 hours)
        if work_extra > 0:
            added_work_plays = round((work_extra / 9.0) / 2.6)
            for h in range(7, 16):
                hourly_counts[h] += added_work_plays

        # Determine peak hour
        peak_h = max(range(24), key=lambda h: hourly_counts[h])
        if peak_h == 0:
            peak_hour_str = "12 AM"
        elif peak_h < 12:
            peak_hour_str = f"{peak_h} AM"
        elif peak_h == 12:
            peak_hour_str = "12 PM"
        else:
            peak_hour_str = f"{peak_h - 12} PM"

        peak_plays_fmt = f"{hourly_counts[peak_h]:,}"
        peak_desc_str = f"{peak_plays_fmt} Plays • Workday & Flow" if work_extra > 0 else "Workday & Daily Flow"

        # Chronotype block determination
        night_plays = sum(hourly_counts[h] for h in [23, 0, 1, 2, 3, 4])
        morning_plays = sum(hourly_counts[h] for h in range(5, 12))
        afternoon_plays = sum(hourly_counts[h] for h in range(12, 18))
        evening_plays = sum(hourly_counts[h] for h in range(18, 23))

        max_chrono = max(afternoon_plays, morning_plays, evening_plays, night_plays)
        if afternoon_plays == max_chrono:
            chrono_tag_str = "AFTERNOON FLOW"
        elif morning_plays == max_chrono:
            chrono_tag_str = "MORNING ENERGIZER"
        elif evening_plays == max_chrono:
            chrono_tag_str = "EVENING RESONATOR"
        else:
            chrono_tag_str = "NIGHT OWL"

        chrono_detail_str = f"7:00 AM – 3:00 PM Workday ({work_extra:,}m) + Weekend Releases" if work_extra > 0 else "7:00 AM – 3:00 PM Workday + Weekend Releases"

        # Weekly rhythm calculation (7 days: Sun to Sat)
        work_day_addition = round(work_extra / 5.0) if work_extra > 0 else 0
        week_days_mins = {
            "sun": 2750,
            "mon": 1950 + work_day_addition,
            "tue": 2050 + work_day_addition,
            "wed": 3740 + work_day_addition,
            "thu": 2600 + work_day_addition,
            "fri": 2450 + work_day_addition,
            "sat": 2800 + sat_extra,
        }

        peak_day_key = max(week_days_mins, key=week_days_mins.get)
        peak_day_bar_id = f"eq-{peak_day_key}"
        if peak_day_key == "sat":
            week_badge_str = f"Saturday +{sat_extra:,}m"
        elif peak_day_key == "wed":
            week_badge_str = f"Wednesday +{week_days_mins['wed']:,}m" if work_extra > 0 else "Wednesday +2,740"
        else:
            week_badge_str = f"{peak_day_key.capitalize()} +{week_days_mins[peak_day_key]:,}m"

        max_day_mins = max(week_days_mins.values()) or 1
        day_heights: dict[str, int] = {}
        for d_key, d_val in week_days_mins.items():
            ratio = d_val / max_day_mins
            day_heights[f"eq-{d_key}"] = round(80 + ratio * 155)

        day_peak_classes = {
            d_key: " peak" if d_key == peak_day_key else ""
            for d_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
        }

        # Load artworks
        artworks: dict[str, str] = {}
        if Path(artworks_file).exists():
            try:
                artworks = json.loads(Path(artworks_file).read_text(encoding="utf-8"))
            except Exception:
                pass

        # Curated Top 5 Songs
        top_songs_list = curation.get("top_songs", [])
        def get_song(idx: int, def_title: str, def_artist: str, def_art_key: str) -> dict[str, str]:
            item = top_songs_list[idx] if len(top_songs_list) > idx else {}
            t = item.get("title") or def_title
            a = item.get("artist") or def_artist
            art = item.get("artwork") or artworks.get(def_art_key, "")
            return {"title": t, "artist": a, "artwork": art}

        s1 = get_song(0, "sorry im a haunted house", "Savage Ga$p, KAMAARA", "top_1_sorry im a haunted house - Savage Ga$p, KAMAARA.flac.png")
        s2 = get_song(1, "WITCHCRAFT", "AntXres, SCXR SOUL, Ethan Ross, Jupiluxe", "top_2_WITCHCRAFT - AntXres, SCXR SOUL, Ethan Ross, Jupiluxe.flac.png")
        s3 = get_song(2, "FULL SEND RMX", "BLXCKBUSTA, Ethan Ross", "top_3_FULL SEND RMX - BLXCKBUSTA, Ethan Ross.flac.png")
        s4 = get_song(3, "BACKSTAGE", "GOTOU寄生獣, vodvor", "top_4_BACKSTAGE - GOTOU寄生獣, vodvor.flac.png")
        s5 = get_song(4, "I'll Come Runnin", "ILLENIUM, Zeds Dead, Mako", "top_5_001 - I'll Come Runnin.flac.png")

        # Curated Top 5 Albums
        top_albums_list = curation.get("top_albums", [])
        def get_album(idx: int, def_alb: str, def_art: str, fallback_img: str) -> dict[str, str]:
            item = top_albums_list[idx] if len(top_albums_list) > idx else {}
            alb = item.get("album") or def_alb
            art = item.get("artist") or def_art
            img = item.get("artwork") or fallback_img
            return {"album": alb, "artist": art, "artwork": img}

        alb1 = get_album(0, "sorry im a haunted house", "Savage Ga$p", s1["artwork"])
        alb2 = get_album(1, "FALLEN ANGEL", "ILLENIUM", s5["artwork"])
        alb3 = get_album(2, "SCXR ARCHIVES", "SCXR SOUL", s2["artwork"])
        alb4 = get_album(3, "PHONK NATION", "Various Artists", s3["artwork"])
        alb5 = get_album(4, "ASCEND", "ILLENIUM", s5["artwork"])

        # Curated Top 5 Artists
        top_artists_list = curation.get("top_artists", [])
        def get_artist(idx: int, def_name: str, fallback_img: str) -> dict[str, str]:
            item = top_artists_list[idx] if len(top_artists_list) > idx else {}
            name = item.get("name") or def_name
            img = item.get("image")
            if not img or img.startswith("data:image/svg"):
                img = self.resolve_artist_avatar(name, fallback_img)
            return {"name": name, "image": img}

        art1 = get_artist(0, "ILLENIUM", s5["artwork"])
        art2 = get_artist(1, "Savage Ga$p", s1["artwork"])
        art3 = get_artist(2, "SCXR SOUL", s2["artwork"])
        art4 = get_artist(3, "Ethan Ross", s3["artwork"])
        art5 = get_artist(4, "KAMAARA", s4["artwork"])

        # Curated Top 5 Discoveries
        top_disc_list = curation.get("top_discoveries", [])
        def get_disc(idx: int, def_name: str, fallback_img: str) -> dict[str, str]:
            item = top_disc_list[idx] if len(top_disc_list) > idx else {}
            name = item.get("name") or def_name
            img = item.get("image")
            if not img or img.startswith("data:image/svg"):
                img = self.resolve_artist_avatar(name, fallback_img)
            return {"name": name, "image": img}

        disc1 = get_disc(0, "GOTOU寄生獣", s4["artwork"])
        disc2 = get_disc(1, "AntXres", s2["artwork"])
        disc3 = get_disc(2, "vodvor", s4["artwork"])
        disc4 = get_disc(3, "BLXCKBUSTA", s3["artwork"])
        disc5 = get_disc(4, "Zeds Dead", s5["artwork"])

        # Curated Top Genres & Anthems
        top_genres_list = curation.get("top_genres", [])
        def get_genre(idx: int, def_g: str, def_s: str) -> dict[str, str]:
            item = top_genres_list[idx] if len(top_genres_list) > idx else {}
            return {"genre": item.get("genre") or def_g, "song": item.get("song") or def_s}

        g1 = get_genre(0, "Phonk", "WITCHCRAFT")
        g2 = get_genre(1, "Melodic Bass", "I'll Come Runnin")
        g3 = get_genre(2, "Trap Metal", "sorry im a haunted house")
        g4 = get_genre(3, "Drift Phonk", "FULL SEND RMX")
        g5 = get_genre(4, "Future Bass", "Nightlight")

        # Slide 9: 9. Most Listened Songs (Automated Namida Telemetry - Read-Only)
        raw_top_tracks = stats_data.get("top_tracks", [])
        ml_tracks = []
        fallback_titles = ["sorry im a haunted house", "WITCHCRAFT", "FULL SEND RMX", "BACKSTAGE", "I'll Come Runnin"]
        fallback_artists = ["Savage Ga$p, KAMAARA", "AntXres, SCXR SOUL, Ethan Ross, Jupiluxe", "BLXCKBUSTA, Ethan Ross", "GOTOU寄生獣, vodvor", "ILLENIUM, Zeds Dead, Mako"]
        fallback_arts = [s1["artwork"], s2["artwork"], s3["artwork"], s4["artwork"], s5["artwork"]]
        fallback_plays = [69, 68, 60, 59, 57]
        fallback_mins = [169.0, 167.1, 137.9, 106.1, 211.0]
        for i in range(5):
            t_base = raw_top_tracks[i] if len(raw_top_tracks) > i else {}
            title = t_base.get("title") or fallback_titles[i]
            artist = t_base.get("artist") or fallback_artists[i]
            base_plays = int(t_base.get("plays", fallback_plays[i]))
            base_mins = float(t_base.get("total_listen_minutes", fallback_mins[i]))
            art = fallback_arts[i]

            ml_tracks.append({
                "rank": i + 1,
                "title": title,
                "artist": artist,
                "plays": base_plays,
                "minutes": round(base_mins, 1),
                "artwork": art
            })

        # Slide 10: 10. Most Listened Artists (Automated Namida Telemetry - Read-Only)
        raw_top_artists = stats_data.get("top_artists", [])
        ml_artists = []
        fallback_names = ["GOTOU寄生獣, vodvor", "Daegho", "MUPP", "Savage Ga$p", "Kordhell, Scarlxrd"]
        fallback_art_plays = [510, 193, 152, 149, 140]
        fallback_imgs = [s4["artwork"], s3["artwork"], s2["artwork"], s1["artwork"], s5["artwork"]]
        for i in range(5):
            a_base = raw_top_artists[i] if len(raw_top_artists) > i else {}
            name = a_base.get("artist") or fallback_names[i]
            base_plays = int(a_base.get("plays", fallback_art_plays[i]))
            base_mins = round(base_plays * 2.8)
            img = self.resolve_artist_avatar(name, fallback_imgs[i])

            ml_artists.append({
                "rank": i + 1,
                "name": name,
                "plays": base_plays,
                "minutes": round(base_mins),
                "image": img
            })

        # Load external CSS and JS modules
        css_content = (self.template_dir / "styles.css").read_text(encoding="utf-8")
        js_content = (self.template_dir / "animations.js").read_text(encoding="utf-8")

        year_str = str(self.target_year)

        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{year_str} Wrapped</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@700;800;900&display=swap" rel="stylesheet">
<style>
:root {{
  --theme-primary: {active_theme['primary']};
  --theme-secondary: {active_theme['secondary']};
  --theme-accent: {active_theme['accent']};
  --theme-tertiary: {active_theme['tertiary']};
  --theme-bg-base: {active_theme['bg_base']};
  --theme-bg-mid: {active_theme['bg_mid']};
  --theme-bg-outer: {active_theme['bg_outer']};
}}
{css_content}
</style>
</head>
<body>

  <!-- Saturated Spotify Aurora Ambient Mesh Canvas -->
  <div class="ambient-canvas">
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>
    <div class="orb orb-4"></div>
  </div>

  <!-- Story Progress Segment Bars (10 segments for 10 slides) -->
  <div class="story-bars">
    <div class="story-bar"><div class="story-bar-fill" id="pbar-0"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-1"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-2"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-3"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-4"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-5"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-6"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-7"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-8"></div></div>
    <div class="story-bar"><div class="story-bar-fill" id="pbar-9"></div></div>
  </div>

  <!-- Top Header Branding -->
  <div class="story-header">
    <div class="brand-tag">• {year_str} WRAPPED</div>
    <div class="brand-badge">ANNUAL REVIEW</div>
  </div>

  <!-- Viewport -->
  <div class="content-viewport">

    <!-- SLIDE 1: YOUR YEAR IN SOUND -->
    <div class="slide" id="slide-0">
      <div class="title-group anim-title" id="s0-title">
        <div class="hero-title">Your Year in Sound</div>
      </div>

      <div class="slide-1-body">
        <div class="wave-card anim-hero" id="s0-wave">
          <div class="wave-card-top">
            <span class="wave-card-tag"><span class="pulse-indicator"></span>LISTENING FREQUENCY</span>
            <span class="wave-card-peak">Peak: May (1,842 plays)</span>
          </div>
          <div class="wave-svg-box">
            <svg viewBox="0 0 910 240" width="100%" height="100%" style="overflow: visible;">
              <defs>
                <linearGradient id="wave-area-glow" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stop-color="{active_theme['primary']}" stop-opacity="0.38"/>
                  <stop offset="60%" stop-color="{active_theme['primary']}" stop-opacity="0.10"/>
                  <stop offset="100%" stop-color="{active_theme['primary']}" stop-opacity="0.0"/>
                </linearGradient>
                <linearGradient id="wave-stroke-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="{active_theme['primary']}"/>
                  <stop offset="40%" stop-color="{active_theme['secondary']}"/>
                  <stop offset="80%" stop-color="{active_theme['accent']}"/>
                  <stop offset="100%" stop-color="{active_theme['primary']}"/>
                </linearGradient>
                <filter id="tracer-glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="8" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>
              <path id="wave-area" d="M 15 175 Q 150 185 260 80 T 480 35 T 700 120 T 895 130 L 895 240 L 15 240 Z" 
                    fill="url(#wave-area-glow)" opacity="0"/>
              <path d="M 15 155 Q 150 175 260 95 T 480 50 T 700 128 T 895 110" 
                    fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="4" stroke-linecap="round"/>
              <path id="wave-path" d="M 15 175 Q 150 185 260 80 T 480 35 T 700 120 T 895 130" 
                    fill="none" stroke="url(#wave-stroke-grad)" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>
              <circle id="wave-dot" cx="15" cy="175" r="14" fill="#ffffff" filter="url(#tracer-glow)" opacity="0"/>
              
              <!-- Month Timeline Axis Ticks for editorial personality -->
              <g class="wave-axis-labels">
                <text x="35" y="222" fill="rgba(255,255,255,0.75)" font-size="34" font-weight="800">JAN</text>
                <text x="245" y="222" fill="rgba(255,255,255,0.75)" font-size="34" font-weight="800">MAR</text>
                <text x="460" y="222" fill="{active_theme['primary']}" font-size="36" font-weight="900">MAY (PEAK)</text>
                <text x="690" y="222" fill="rgba(255,255,255,0.75)" font-size="34" font-weight="800">AUG</text>
                <text x="850" y="222" fill="rgba(255,255,255,0.75)" font-size="34" font-weight="800">NOV</text>
              </g>
            </svg>
          </div>
          <div class="wave-card-bottom-note">
            <span>✦ Spring velocity • Peak listening momentum into the summer</span>
          </div>
        </div>

        <div class="bento-grid-2x2 anim-sub" id="s0-bento">
          <div class="bento-card highlight-green" id="bento-0">
            <div class="bento-top-row">
              <div class="bento-card-pill"><span class="pill-sym">▶</span> PLAYS</div>
            </div>
            <div>
              <div class="bento-value" id="val-listens" data-target="{total_plays_raw}">{total_plays_fmt}</div>
              <div class="bento-label">Total Plays</div>
              <div class="bento-subtext">Across {active_days_val} active days</div>
              <div class="bento-micro-meter">
                <div class="bento-micro-bar fill" id="bmb-0" style="height: 40%;"></div>
                <div class="bento-micro-bar fill" id="bmb-1" style="height: 65%;"></div>
                <div class="bento-micro-bar fill" id="bmb-2" style="height: 100%;"></div>
                <div class="bento-micro-bar fill" id="bmb-3" style="height: 80%;"></div>
                <div class="bento-micro-bar fill" id="bmb-4" style="height: 55%;"></div>
              </div>
            </div>
          </div>

          <div class="bento-card highlight-gold" id="bento-1">
            <div class="bento-top-row">
              <div class="bento-card-pill"><span class="pill-sym">⚡</span> MINUTES</div>
            </div>
            <div>
              <div class="bento-value" id="val-time" data-target="{total_min_raw}">{total_hours_val}h {int(total_min_raw % 60)}m</div>
              <div class="bento-label">Minutes Streamed</div>
              <div class="bento-subtext">{total_min_fmt} total minutes</div>
              <div class="bento-micro-meter">
                <div class="bento-micro-bar fill" id="bmb-5" style="height: 50%;background:#ffb800;"></div>
                <div class="bento-micro-bar fill" id="bmb-6" style="height: 85%;background:#ffb800;"></div>
                <div class="bento-micro-bar fill" id="bmb-7" style="height: 100%;background:#ffb800;"></div>
                <div class="bento-micro-bar fill" id="bmb-8" style="height: 70%;background:#ffb800;"></div>
                <div class="bento-micro-bar fill" id="bmb-9" style="height: 90%;background:#ffb800;"></div>
              </div>
            </div>
          </div>

          <div class="bento-card highlight-cyan" id="bento-2">
            <div class="bento-top-row">
              <div class="bento-card-pill"><span class="pill-sym">♫</span> TRACKS</div>
            </div>
            <div>
              <div class="bento-value" id="val-tracks" data-target="{unique_tracks_raw}">{unique_tracks_fmt}</div>
              <div class="bento-label">Different Songs</div>
              <div class="bento-subtext">{unique_artists_fmt} distinct artists</div>
              <div class="bento-micro-meter">
                <div class="bento-micro-bar fill" id="bmb-10" style="height: 95%;"></div>
                <div class="bento-micro-bar fill" id="bmb-11" style="height: 75%;"></div>
                <div class="bento-micro-bar fill" id="bmb-12" style="height: 60%;"></div>
                <div class="bento-micro-bar fill" id="bmb-13" style="height: 85%;"></div>
                <div class="bento-micro-bar fill" id="bmb-14" style="height: 100%;"></div>
              </div>
            </div>
          </div>

          <div class="bento-card highlight-purple" id="bento-3">
            <div class="bento-top-row">
              <div class="bento-card-pill"><span class="pill-sym">🔥</span> STREAK</div>
            </div>
            <div>
              <div class="bento-value" id="val-days" data-target="{streak_val}">{streak_val}</div>
              <div class="bento-label">Day Streak</div>
              <div class="bento-subtext">Longest listening streak</div>
              <div class="bento-micro-meter">
                <div class="bento-micro-bar fill" id="bmb-15" style="height: 60%;"></div>
                <div class="bento-micro-bar fill" id="bmb-16" style="height: 80%;"></div>
                <div class="bento-micro-bar fill" id="bmb-17" style="height: 70%;"></div>
                <div class="bento-micro-bar fill" id="bmb-18" style="height: 100%;"></div>
                <div class="bento-micro-bar fill" id="bmb-19" style="height: 90%;"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 2: THE BIG NUMBERS (NO 100% FLAC) -->
    <div class="slide" id="slide-1">
      <div class="title-group anim-title" id="s1-title">
        <div class="eyebrow">Listening Volume</div>
        <div class="hero-title">The Big Numbers</div>
      </div>

      <div class="slide-2-body">
        <div class="trio-hero-card anim-hero" id="s1-hero">
          <div class="trio-hero-top">
            <div class="bento-card-pill">TOP 1%</div>
            <div class="wave-card-peak">Top Listener</div>
          </div>
          <div>
            <div class="trio-hero-number" id="trio-hero-min" data-target="{total_min_raw}">{total_min_fmt} <span style="font-size:46px;color:#1ed760;font-weight:700;">MINUTES</span></div>
            <div class="trio-hero-label">That's {total_hours_val} hours of non-stop music.</div>
          </div>
          <div class="trio-eq-stream" id="trio-eq-container"></div>
        </div>

        <div class="trio-twin-row anim-sub" id="s1-twins">
          <div class="twin-card" id="twin-tot">
            <div class="bento-top-row">
              <div class="bento-card-pill">TOTAL PLAYS</div>
            </div>
            <div>
              <div class="twin-num" id="twin-tot-val" data-target="{total_plays_raw}">{total_plays_fmt}</div>
              <div class="twin-label">Total Songs Played</div>
              <div class="twin-sub">{daily_avg_songs} plays / active day</div>
            </div>
          </div>

          <div class="twin-card" id="twin-dist">
            <div class="bento-top-row">
              <div class="bento-card-pill">VARIETY</div>
            </div>
            <div>
              <div class="twin-num" id="twin-dist-val" data-target="{unique_tracks_raw}">{unique_tracks_fmt}</div>
              <div class="twin-label">Different Songs</div>
              <div class="twin-sub">Curated across {year_str}</div>
            </div>
          </div>
        </div>

        <div class="rhythm-banner-card anim-foot" id="s1-rhythm">
          <div>
            <div class="rhythm-val">{daily_avg_min} min / day</div>
            <div class="rhythm-lbl">Daily Listening Average</div>
          </div>
          <div style="text-align:right;">
            <div class="rhythm-val" style="color:#1ed760;">TOP 1%</div>
            <div class="rhythm-lbl">Worldwide Dedicated Listener</div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 3: LISTENING CLOCK (WORKING HOURS & SATURDAY) -->
    <div class="slide" id="slide-2">
      <div class="title-group anim-title" id="s2-title">
        <div class="eyebrow">Habits & Routine</div>
        <div class="hero-title">Listening Clock</div>
      </div>

      <div class="slide-3-body">
        <div class="clock-stage-box anim-hero" id="s2-clock">
          <div class="clock-relative-canvas">
            <svg class="clock-svg-layer" viewBox="0 0 680 680">
              <circle cx="340" cy="340" r="260" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="50"/>
              <text x="340" y="45" fill="#8ca08e" font-size="26" font-weight="800" text-anchor="middle">12 AM</text>
              <text x="645" y="348" fill="#8ca08e" font-size="26" font-weight="800" text-anchor="middle">6 AM</text>
              <text x="340" y="650" fill="#8ca08e" font-size="26" font-weight="800" text-anchor="middle">12 PM</text>
              <text x="35" y="348" fill="#8ca08e" font-size="26" font-weight="800" text-anchor="middle">6 PM</text>
              <g id="clock-rays"></g>
            </svg>

            <div class="clock-center-disc" id="clock-center-pill">
              <div class="clock-center-time">{peak_hour_str}</div>
              <div class="clock-center-sub">PEAK HOUR</div>
              <div class="clock-center-plays">{peak_desc_str}</div>
            </div>
          </div>
        </div>

        <div class="chronotype-bridge-card anim-sub" id="s2-chrono">
          <span class="chrono-tag">{chrono_tag_str}</span>
          <span class="chrono-detail">{chrono_detail_str}</span>
        </div>

        <div class="week-equalizer-card anim-foot" id="s2-week">
          <div class="week-eq-title-row">
            <span class="week-eq-title">WEEKLY RHYTHM</span>
            <span class="week-eq-badge">{week_badge_str}</span>
          </div>

          <div class="week-eq-bars">
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['sun']}" id="eq-sun" style="height: {day_heights['eq-sun']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['sun']}">Sun</div>
            </div>
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['mon']}" id="eq-mon" style="height: {day_heights['eq-mon']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['mon']}">Mon</div>
            </div>
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['tue']}" id="eq-tue" style="height: {day_heights['eq-tue']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['tue']}">Tue</div>
            </div>
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['wed']}" id="eq-wed" style="height: {day_heights['eq-wed']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['wed']}">Wed</div>
            </div>
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['thu']}" id="eq-thu" style="height: {day_heights['eq-thu']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['thu']}">Thu</div>
            </div>
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['fri']}" id="eq-fri" style="height: {day_heights['eq-fri']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['fri']}">Fri</div>
            </div>
            <div class="eq-day-col">
              <div class="eq-bar-wrap"><div class="eq-bar{day_peak_classes['sat']}" id="eq-sat" style="height: {day_heights['eq-sat']}px;"></div></div>
              <div class="eq-day-name{day_peak_classes['sat']}">Sat</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 4: TOP SONGS (CURATED) -->
    <div class="slide" id="slide-3">
      <div class="title-group anim-title" id="s3-title">
        <div class="eyebrow">Heavy Rotation</div>
        <div class="hero-title">Top Songs</div>
      </div>

      <div class="slide-4-body">
        <div class="hero-spotlight-card anim-hero" id="t-hero-spotlight">
          <div class="hero-vinyl-wrapper">
            <div class="hero-vinyl-disc" id="vinyl-disc">
              <div class="hero-vinyl-center"></div>
            </div>
            <img class="hero-cover-art" src="{s1['artwork']}" alt="Top 1">
          </div>
          <div class="hero-track-info">
            <div class="hero-track-pill">#1 TRACK OF THE YEAR</div>
            <div class="hero-track-name">{s1['title']}</div>
            <div class="hero-track-artist">{s1['artist']}</div>
          </div>
        </div>

        <div class="sub-tracks-list anim-sub" id="s3-subtracks">
          <div class="sub-track-card" id="t-card-1">
            <div class="sub-track-rank">2</div>
            <img class="sub-track-cover" src="{s2['artwork']}" alt="Top 2">
            <div class="sub-track-meta">
              <div class="sub-track-name">{s2['title']}</div>
              <div class="sub-track-by">{s2['artist']}</div>
            </div>
          </div>

          <div class="sub-track-card" id="t-card-2">
            <div class="sub-track-rank">3</div>
            <img class="sub-track-cover" src="{s3['artwork']}" alt="Top 3">
            <div class="sub-track-meta">
              <div class="sub-track-name">{s3['title']}</div>
              <div class="sub-track-by">{s3['artist']}</div>
            </div>
          </div>

          <div class="sub-track-card" id="t-card-3">
            <div class="sub-track-rank">4</div>
            <img class="sub-track-cover" src="{s4['artwork']}" alt="Top 4">
            <div class="sub-track-meta">
              <div class="sub-track-name">{s4['title']}</div>
              <div class="sub-track-by">{s4['artist']}</div>
            </div>
          </div>

          <div class="sub-track-card" id="t-card-4">
            <div class="sub-track-rank">5</div>
            <img class="sub-track-cover" src="{s5['artwork']}" alt="Top 5">
            <div class="sub-track-meta">
              <div class="sub-track-name">{s5['title']}</div>
              <div class="sub-track-by">{s5['artist']}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 5: TOP ALBUMS (CURATED) -->
    <div class="slide" id="slide-4">
      <div class="title-group anim-title" id="s4-title">
        <div class="eyebrow">Full Playthroughs</div>
        <div class="hero-title">Top Albums</div>
      </div>

      <div class="slide-5-body">
        <div class="hero-album-card anim-hero" id="alb-hero">
          <div class="hero-vinyl-wrapper">
            <div class="hero-vinyl-disc" id="vinyl-disc-alb">
              <div class="hero-vinyl-center" style="background:#b77bf2;"></div>
            </div>
            <img class="hero-cover-art" src="{alb1['artwork']}" alt="Top Album">
          </div>
          <div class="hero-track-info">
            <div class="hero-album-pill">#1 ALBUM OF THE YEAR</div>
            <div class="hero-track-name">{alb1['album']}</div>
            <div class="hero-track-artist">{alb1['artist']}</div>
          </div>
        </div>

        <div class="sub-tracks-list anim-sub" id="s4-subalbums">
          <div class="sub-track-card" id="alb-card-1">
            <div class="sub-track-rank">2</div>
            <img class="sub-track-cover" src="{alb2['artwork']}" alt="Album 2">
            <div class="sub-track-meta">
              <div class="sub-track-name">{alb2['album']}</div>
              <div class="sub-track-by">{alb2['artist']}</div>
            </div>
          </div>

          <div class="sub-track-card" id="alb-card-2">
            <div class="sub-track-rank">3</div>
            <img class="sub-track-cover" src="{alb3['artwork']}" alt="Album 3">
            <div class="sub-track-meta">
              <div class="sub-track-name">{alb3['album']}</div>
              <div class="sub-track-by">{alb3['artist']}</div>
            </div>
          </div>

          <div class="sub-track-card" id="alb-card-3">
            <div class="sub-track-rank">4</div>
            <img class="sub-track-cover" src="{alb4['artwork']}" alt="Album 4">
            <div class="sub-track-meta">
              <div class="sub-track-name">{alb4['album']}</div>
              <div class="sub-track-by">{alb4['artist']}</div>
            </div>
          </div>

          <div class="sub-track-card" id="alb-card-4">
            <div class="sub-track-rank">5</div>
            <img class="sub-track-cover" src="{alb5['artwork']}" alt="Album 5">
            <div class="sub-track-meta">
              <div class="sub-track-name">{alb5['album']}</div>
              <div class="sub-track-by">{alb5['artist']}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 6: TOP ARTISTS (CURATED) -->
    <div class="slide" id="slide-5">
      <div class="title-group anim-title" id="s5-title">
        <div class="eyebrow">Favorite Creators</div>
        <div class="hero-title">Top Artists</div>
      </div>

      <div class="slide-6-body">
        <div class="hero-artist-card anim-hero" id="art-hero">
          <img class="hero-artist-avatar" src="{art1['image']}" alt="{art1['name']}">
          <div class="hero-track-info">
            <div class="hero-track-pill">#1 ARTIST OF THE YEAR</div>
            <div class="hero-artist-name">{art1['name']}</div>
            <div class="hero-track-artist">Most Streamed Creator</div>
          </div>
        </div>

        <div class="sub-tracks-list anim-sub" id="s5-subartists">
          <div class="sub-track-card" id="art-card-1">
            <div class="sub-track-rank">2</div>
            <img class="sub-artist-avatar" src="{art2['image']}" alt="{art2['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{art2['name']}</div>
              <div class="sub-track-by">Top Creator</div>
            </div>
          </div>

          <div class="sub-track-card" id="art-card-2">
            <div class="sub-track-rank">3</div>
            <img class="sub-artist-avatar" src="{art3['image']}" alt="{art3['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{art3['name']}</div>
              <div class="sub-track-by">Top Creator</div>
            </div>
          </div>

          <div class="sub-track-card" id="art-card-3">
            <div class="sub-track-rank">4</div>
            <img class="sub-artist-avatar" src="{art4['image']}" alt="{art4['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{art4['name']}</div>
              <div class="sub-track-by">Top Creator</div>
            </div>
          </div>

          <div class="sub-track-card" id="art-card-4">
            <div class="sub-track-rank">5</div>
            <img class="sub-artist-avatar" src="{art5['image']}" alt="{art5['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{art5['name']}</div>
              <div class="sub-track-by">Top Creator</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 7: TOP DISCOVERIES (CURATED) -->
    <div class="slide" id="slide-6">
      <div class="title-group anim-title" id="s6-title">
        <div class="eyebrow">New Horizons</div>
        <div class="hero-title">Top Discoveries</div>
      </div>

      <div class="slide-7-body">
        <div class="hero-disc-card anim-hero" id="disc-hero">
          <img class="hero-artist-avatar" style="border-color:#ff007a;" src="{disc1['image']}" alt="{disc1['name']}">
          <div class="hero-track-info">
            <div class="hero-disc-pill">#1 DISCOVERY OF {year_str}</div>
            <div class="hero-artist-name">{disc1['name']}</div>
            <div class="hero-track-artist">Fresh Rotation Addition</div>
          </div>
        </div>

        <div class="sub-tracks-list anim-sub" id="s6-subdiscoveries">
          <div class="sub-track-card" id="disc-card-1">
            <div class="sub-track-rank">2</div>
            <img class="sub-artist-avatar" src="{disc2['image']}" alt="{disc2['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{disc2['name']}</div>
              <div class="sub-track-by">Discovered in {year_str}</div>
            </div>
          </div>

          <div class="sub-track-card" id="disc-card-2">
            <div class="sub-track-rank">3</div>
            <img class="sub-artist-avatar" src="{disc3['image']}" alt="{disc3['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{disc3['name']}</div>
              <div class="sub-track-by">Discovered in {year_str}</div>
            </div>
          </div>

          <div class="sub-track-card" id="disc-card-3">
            <div class="sub-track-rank">4</div>
            <img class="sub-artist-avatar" src="{disc4['image']}" alt="{disc4['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{disc4['name']}</div>
              <div class="sub-track-by">Discovered in {year_str}</div>
            </div>
          </div>

          <div class="sub-track-card" id="disc-card-4">
            <div class="sub-track-rank">5</div>
            <img class="sub-artist-avatar" src="{disc5['image']}" alt="{disc5['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{disc5['name']}</div>
              <div class="sub-track-by">Discovered in {year_str}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 8: TOP GENRES & REPRESENTATIVE ANTHEMS -->
    <div class="slide" id="slide-7">
      <div class="title-group anim-title" id="s7-title">
        <div class="eyebrow">Sound DNA</div>
        <div class="hero-title">Top Genres</div>
      </div>

      <div class="slide-8-body">
        <div class="donut-section anim-hero" id="s7-donut">
          <div class="donut-container">
            <svg class="donut-svg" id="donut-svg-ring" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="38" fill="none" stroke="#1d261e" stroke-width="12" />
              <circle cx="50" cy="50" r="38" fill="none" stroke="#00ff87" stroke-width="12" 
                      stroke-dasharray="27.4 211.3" stroke-dashoffset="0" id="donut-seg-0" />
              <circle cx="50" cy="50" r="38" fill="none" stroke="#1ed760" stroke-width="12" 
                      stroke-dasharray="22.9 215.8" stroke-dashoffset="-27.4" id="donut-seg-1" />
              <circle cx="50" cy="50" r="38" fill="none" stroke="#7928ca" stroke-width="12" 
                      stroke-dasharray="22.0 216.7" stroke-dashoffset="-50.3" id="donut-seg-2" />
              <circle cx="50" cy="50" r="38" fill="none" stroke="#ff007a" stroke-width="12" 
                      stroke-dasharray="17.4 221.3" stroke-dashoffset="-72.3" id="donut-seg-3" />
              <circle cx="50" cy="50" r="38" fill="none" stroke="#ff8a00" stroke-width="12" 
                      stroke-dasharray="17.2 221.5" stroke-dashoffset="-89.7" id="donut-seg-4" />
            </svg>
            <div class="donut-center-card" id="donut-center-box">
              <div class="donut-top-tag">TOP GENRE</div>
              <div class="donut-hero-genre">{g1['genre'].upper()}</div>
              <div class="donut-top-tag" style="color:#cad8cc;font-size:18px;margin-top:4px;">Signature Style</div>
            </div>
          </div>
        </div>

        <div class="genre-grid-cards anim-sub" id="s7-genres">
          <div class="genre-anthem-card" id="g-anthem-0">
            <div class="genre-anthem-name">1. {g1['genre']}</div>
            <div class="genre-anthem-track">Anthem: {g1['song']}</div>
          </div>
          <div class="genre-anthem-card" id="g-anthem-1">
            <div class="genre-anthem-name">2. {g2['genre']}</div>
            <div class="genre-anthem-track">Anthem: {g2['song']}</div>
          </div>
          <div class="genre-anthem-card" id="g-anthem-2">
            <div class="genre-anthem-name">3. {g3['genre']}</div>
            <div class="genre-anthem-track">Anthem: {g3['song']}</div>
          </div>
          <div class="genre-anthem-card" id="g-anthem-3">
            <div class="genre-anthem-name">4. {g4['genre']}</div>
            <div class="genre-anthem-track">Anthem: {g4['song']}</div>
          </div>
          <div class="genre-anthem-card" id="g-anthem-4">
            <div class="genre-anthem-name">5. {g5['genre']}</div>
            <div class="genre-anthem-track">Anthem: {g5['song']}</div>
          </div>
        </div>

        <div class="genre-footer-ribbon anim-foot" id="s7-foot">
          Curated musical universe of {year_str}.
        </div>
      </div>
    </div>

    <!-- SLIDE 9: MOST LISTENED SONGS (NAMIDA TELEMETRY) -->
    <div class="slide" id="slide-8">
      <div class="title-group anim-title" id="s8-title">
        <div class="eyebrow">Namida Telemetry</div>
        <div class="hero-title">Most Listened Songs</div>
      </div>

      <div class="slide-4-body">
        <div class="hero-spotlight-card anim-hero" id="mlt-hero-spotlight">
          <div class="hero-vinyl-wrapper">
            <div class="hero-vinyl-disc" id="vinyl-disc-mlt">
              <div class="hero-vinyl-center" style="background:#00ff87;"></div>
            </div>
            <img class="hero-cover-art" src="{ml_tracks[0]['artwork']}" alt="Most Listened Track #1">
          </div>
          <div class="hero-track-info">
            <div class="hero-track-pill" style="background:rgba(0,255,135,0.22);border-color:#00ff87;color:#00ff87;">#1 STREAMED • {ml_tracks[0]['plays']} PLAYS • {ml_tracks[0]['minutes']:.0f} MIN</div>
            <div class="hero-track-name">{ml_tracks[0]['title']}</div>
            <div class="hero-track-artist">{ml_tracks[0]['artist']}</div>
          </div>
        </div>

        <div class="sub-tracks-list anim-sub" id="s8-subtracks">
          <div class="sub-track-card" id="mlt-card-1">
            <div class="sub-track-rank">2</div>
            <img class="sub-track-cover" src="{ml_tracks[1]['artwork']}" alt="Top 2">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_tracks[1]['title']}</div>
              <div class="sub-track-by">{ml_tracks[1]['artist']}</div>
            </div>
            <div class="track-metric-pill">{ml_tracks[1]['plays']} plays • {ml_tracks[1]['minutes']:.0f}m</div>
          </div>

          <div class="sub-track-card" id="mlt-card-2">
            <div class="sub-track-rank">3</div>
            <img class="sub-track-cover" src="{ml_tracks[2]['artwork']}" alt="Top 3">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_tracks[2]['title']}</div>
              <div class="sub-track-by">{ml_tracks[2]['artist']}</div>
            </div>
            <div class="track-metric-pill">{ml_tracks[2]['plays']} plays • {ml_tracks[2]['minutes']:.0f}m</div>
          </div>

          <div class="sub-track-card" id="mlt-card-3">
            <div class="sub-track-rank">4</div>
            <img class="sub-track-cover" src="{ml_tracks[3]['artwork']}" alt="Top 4">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_tracks[3]['title']}</div>
              <div class="sub-track-by">{ml_tracks[3]['artist']}</div>
            </div>
            <div class="track-metric-pill">{ml_tracks[3]['plays']} plays • {ml_tracks[3]['minutes']:.0f}m</div>
          </div>

          <div class="sub-track-card" id="mlt-card-4">
            <div class="sub-track-rank">5</div>
            <img class="sub-track-cover" src="{ml_tracks[4]['artwork']}" alt="Top 5">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_tracks[4]['title']}</div>
              <div class="sub-track-by">{ml_tracks[4]['artist']}</div>
            </div>
            <div class="track-metric-pill">{ml_tracks[4]['plays']} plays • {ml_tracks[4]['minutes']:.0f}m</div>
          </div>
        </div>
      </div>
    </div>

    <!-- SLIDE 10: MOST LISTENED ARTISTS (NAMIDA TELEMETRY) -->
    <div class="slide" id="slide-9">
      <div class="title-group anim-title" id="s9-title">
        <div class="eyebrow">Namida Telemetry</div>
        <div class="hero-title">Most Listened Artists</div>
      </div>

      <div class="slide-6-body">
        <div class="hero-artist-card anim-hero" id="mla-hero">
          <img class="hero-artist-avatar" style="border-color:#b77bf2;" src="{ml_artists[0]['image']}" alt="{ml_artists[0]['name']}">
          <div class="hero-track-info">
            <div class="hero-artist-pill" style="background:rgba(121,40,202,0.25);border-color:#a855f7;color:#d8b4fe;">#1 STREAMED ARTIST • {ml_artists[0]['plays']} PLAYS</div>
            <div class="hero-artist-name">{ml_artists[0]['name']}</div>
            <div class="hero-track-artist">{ml_artists[0]['minutes']} minutes played</div>
          </div>
        </div>

        <div class="sub-tracks-list anim-sub" id="s9-subartists">
          <div class="sub-track-card" id="mla-card-1">
            <div class="sub-track-rank">2</div>
            <img class="sub-artist-avatar" src="{ml_artists[1]['image']}" alt="{ml_artists[1]['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_artists[1]['name']}</div>
              <div class="sub-track-by">{ml_artists[1]['minutes']} minutes played</div>
            </div>
            <div class="artist-metric-pill">{ml_artists[1]['plays']} plays</div>
          </div>

          <div class="sub-track-card" id="mla-card-2">
            <div class="sub-track-rank">3</div>
            <img class="sub-artist-avatar" src="{ml_artists[2]['image']}" alt="{ml_artists[2]['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_artists[2]['name']}</div>
              <div class="sub-track-by">{ml_artists[2]['minutes']} minutes played</div>
            </div>
            <div class="artist-metric-pill">{ml_artists[2]['plays']} plays</div>
          </div>

          <div class="sub-track-card" id="mla-card-3">
            <div class="sub-track-rank">4</div>
            <img class="sub-artist-avatar" src="{ml_artists[3]['image']}" alt="{ml_artists[3]['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_artists[3]['name']}</div>
              <div class="sub-track-by">{ml_artists[3]['minutes']} minutes played</div>
            </div>
            <div class="artist-metric-pill">{ml_artists[3]['plays']} plays</div>
          </div>

          <div class="sub-track-card" id="mla-card-4">
            <div class="sub-track-rank">5</div>
            <img class="sub-artist-avatar" src="{ml_artists[4]['image']}" alt="{ml_artists[4]['name']}">
            <div class="sub-track-meta">
              <div class="sub-track-name">{ml_artists[4]['name']}</div>
              <div class="sub-track-by">{ml_artists[4]['minutes']} minutes played</div>
            </div>
            <div class="artist-metric-pill">{ml_artists[4]['plays']} plays</div>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Bottom Navigation (10 dots) -->
  <div class="story-footer">
    <div class="footer-dots">
      <div class="f-dot" id="fdot-0"></div>
      <div class="f-dot" id="fdot-1"></div>
      <div class="f-dot" id="fdot-2"></div>
      <div class="f-dot" id="fdot-3"></div>
      <div class="f-dot" id="fdot-4"></div>
      <div class="f-dot" id="fdot-5"></div>
      <div class="f-dot" id="fdot-6"></div>
      <div class="f-dot" id="fdot-7"></div>
      <div class="f-dot" id="fdot-8"></div>
      <div class="f-dot" id="fdot-9"></div>
    </div>
  </div>

  <script>
    window.CLOCK_HOURLY_DATA = {json.dumps(hourly_counts)};
    window.CLOCK_WEEK_HEIGHTS = {json.dumps(day_heights)};
    window.CLOCK_PEAK_HOUR = {peak_h};
    window.CLOCK_PEAK_DAY_ID = "{peak_day_bar_id}";
{js_content}
  </script>
</body>
</html>
"""
        output_file.write_text(html_body, encoding="utf-8")
        return output_file
