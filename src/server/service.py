"""
Web Studio Service Module.
Coordinates curation persistence, storyboard compilation, slice rendering, and FLAC extraction.
Author: Antigravity
Python: 3.13.12
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from src.config import (
    CURATION_JSON_PATH,
    CURRENT_YEAR,
    CUSTOM_VIDEO_PATH,
    DEFAULT_SOUNDTRACK_PATH,
    LEGACY_STATS_JSON_PATH,
    OUTPUT_DIR,
    OUTPUT_VIDEO_PATH,
    PANEL_CONFIGS_DIR,
    RENDERS_DIR,
    ROOT_DIR,
    SLICES_DIR,
    STATS_JSON_PATH,
    STORY_HTML_PATH,
    TEMP_AUDIO_DIR,
)
from src.curator.wizard import CuratorWizard
from src.templates.builder import StoryboardBuilder


class StudioService:
    """Core state and execution coordinator for 2026 Wrapped Web Studio."""

    def __init__(self):
        self.curator = CuratorWizard()
        self.builder = StoryboardBuilder(target_year=CURRENT_YEAR)
        self.current_panel: int = 0
        self.completed_panels: set[int] = set()
        self.is_rendering: bool = False
        self.render_progress: float = 0.0
        self.last_slice_file: Optional[Path] = None

    def get_curation(self) -> dict[str, Any]:
        """Loads live curation data."""
        return self.curator.load_curation_data()

    def get_preview_fps(self) -> int:
        """Returns the globally configured preview framerate (1 to 60 FPS)."""
        curation = self.get_curation()
        try:
            fps = int(curation.get("preview_fps", 1))
            return max(1, min(60, fps))
        except (TypeError, ValueError):
            return 1

    def set_preview_fps(self, fps: int) -> int:
        """Updates and persists the global preview framerate across all previews."""
        clamped = max(1, min(60, int(fps)))
        curation = self.get_curation()
        curation["preview_fps"] = clamped
        CURATION_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        CURATION_JSON_PATH.write_text(json.dumps(curation, indent=2, ensure_ascii=False), encoding="utf-8")
        return clamped

    def get_theme(self) -> dict[str, Any]:
        """Returns the currently active theme palette and background glow colors.
        
        Why: Ensures Web Studio UI and renderer utilize synchronized color palettes.
        """
        curation = self.get_curation()
        default_theme = {
            "id": "aurora",
            "primary": "#00ff87",
            "secondary": "#7928ca",
            "accent": "#ff007a",
            "tertiary": "#00d4ff",
            "bg_base": "#030604",
            "bg_mid": "#0c2616",
            "bg_outer": "#07140b",
        }
        theme = curation.get("theme", {})
        if not isinstance(theme, dict):
            theme = {}
        for k, v in default_theme.items():
            if k not in theme or not theme[k]:
                theme[k] = v
        return theme

    def set_theme(self, theme_data: dict[str, Any]) -> dict[str, Any]:
        """Updates and persists the background theme palette, immediately rebuilding story.html.
        
        Why: Allows real-time visual feedback in the Web Studio preview iframe and applies
        the custom palette to subsequent slice and full-length video renders.
        """
        current_theme = self.get_theme()
        current_theme.update(theme_data)
        curation = self.get_curation()
        curation["theme"] = current_theme
        CURATION_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        CURATION_JSON_PATH.write_text(json.dumps(curation, indent=2, ensure_ascii=False), encoding="utf-8")
        self.builder.build(output_file=STORY_HTML_PATH)
        return current_theme

    def update_panel(self, panel_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Updates specific panel data and re-compiles the HTML storyboard.

        Why: Immediate recompilation allows the right-side preview pane
        to reflect user modifications with zero latency.
        """
        curation = self.get_curation()

        if panel_id == 0:
            # Your Year in Sound: Spotify Extra Minutes, Plays, Songs, Streak
            sp = curation.setdefault("spotify_additions", {})
            if "extra_minutes" in data:
                sp["extra_minutes"] = int(data["extra_minutes"])
            if "extra_plays" in data:
                sp["extra_plays"] = int(data["extra_plays"])
            if "extra_songs" in data:
                sp["extra_songs"] = int(data["extra_songs"])
            if "streak_days" in data:
                sp["streak_days"] = int(data["streak_days"])

        elif panel_id == 1:
            # The Big Numbers
            bignum = curation.setdefault("big_numbers", {})
            bignum.update(data)

        elif panel_id == 2:
            # Listening Clock: Workday and Saturday minutes
            clock = curation.setdefault("listening_clock", {})
            if "workday_extra_minutes" in data:
                clock["workday_extra_minutes"] = int(data["workday_extra_minutes"])
                clock["work_hours_minutes_total"] = int(data["workday_extra_minutes"])
            elif "work_hours_minutes_total" in data:
                clock["work_hours_minutes_total"] = int(data["work_hours_minutes_total"])
                clock["workday_extra_minutes"] = int(data["work_hours_minutes_total"])
            if "saturday_extra_minutes" in data:
                clock["saturday_extra_minutes"] = int(data["saturday_extra_minutes"])

        elif panel_id == 3:
            # Top Songs (list of 5 songs)
            if "top_songs" in data and isinstance(data["top_songs"], list):
                curation["top_songs"] = data["top_songs"]

        elif panel_id == 4:
            # Top Albums (list of 5 albums)
            if "top_albums" in data and isinstance(data["top_albums"], list):
                curation["top_albums"] = data["top_albums"]

        elif panel_id == 5:
            # Top Artists (list of 5 artists)
            if "top_artists" in data and isinstance(data["top_artists"], list):
                curation["top_artists"] = data["top_artists"]

        elif panel_id == 6:
            # Top Discoveries (list of 5 discoveries)
            if "top_discoveries" in data and isinstance(data["top_discoveries"], list):
                curation["top_discoveries"] = data["top_discoveries"]

        elif panel_id == 7:
            # Top Genres (list of 5 genres + anthems with optional local paths)
            if "top_genres" in data and isinstance(data["top_genres"], list):
                curation["top_genres"] = data["top_genres"]

        elif panel_id == 8:
            # 9. Most Listened Songs: automated Namida telemetry (read-only)
            pass

        elif panel_id == 9:
            # 10. Most Listened Artists: automated Namida telemetry (read-only)
            pass

        # Per-slide audio configuration (applicable to all slides 0 to 9)
        if "slide_audio" in data and isinstance(data["slide_audio"], dict):
            slide_audio = curation.setdefault("slide_audio", {})
            raw_vol = float(data["slide_audio"].get("volume", 1.0))
            if raw_vol > 1.0:
                raw_vol = raw_vol / 100.0
            slide_audio[str(panel_id)] = {
                "path": data["slide_audio"].get("path", ""),
                "start_sec": float(data["slide_audio"].get("start_sec", 0.0)),
                "volume": round(max(0.0, min(1.0, raw_vol)), 3),
            }

        # Persist to disk (in output/data/ directory which is git-ignored)
        CURATION_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        CURATION_JSON_PATH.write_text(json.dumps(curation, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # Also write a per-panel snapshot backup inside output/data/panel_configs/
        PANEL_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        panel_snap_file = PANEL_CONFIGS_DIR / f"panel_{panel_id}_config.json"
        panel_snap_file.write_text(json.dumps({
            "panel_id": panel_id,
            "saved_data": data,
            "full_curation_snapshot": curation
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        self.completed_panels.add(panel_id)

        # Recompile storyboard HTML
        self.builder.build(output_file=STORY_HTML_PATH)
        return curation

    def save_panel_local(self, panel_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """Saves current panel data locally into non-committed JSON files."""
        curation = self.update_panel(panel_id, data)
        snapshot_file = PANEL_CONFIGS_DIR / f"panel_{panel_id}_config.json"
        return {
            "status": "success",
            "panel_id": panel_id,
            "curation_path": str(CURATION_JSON_PATH),
            "snapshot_path": str(snapshot_file),
            "is_git_ignored": True,
            "message": f"Panel {panel_id + 1} configuration saved locally to {CURATION_JSON_PATH.name} (git-ignored)."
        }

    def save_video_to_disk(
        self,
        target_path_str: str,
        panel_id: Optional[int] = None,
        selected_panels: Optional[list[int]] = None
    ) -> dict[str, Any]:
        """Copies or exports the rendered MP4 video to a user-specified destination path on disk.

        Why: Allows the user to save the resulting video directly to their Desktop,
        downloads, or any custom folder outside or inside the workspace.
        """
        import shutil

        target_p = Path(target_path_str.strip(' "\''))
        if not target_p.is_absolute():
            target_p = (ROOT_DIR / target_p).resolve()

        target_p.parent.mkdir(parents=True, exist_ok=True)

        # Find best candidate source video prioritizing specific matches over generic fallbacks
        source_video: Optional[Path] = None
        if panel_id is not None:
            single_path = SLICES_DIR / f"wrapped_slice_single_{panel_id}.mp4"
            slice_path = SLICES_DIR / f"wrapped_slice_panel_{panel_id}.mp4"
            if single_path.exists():
                source_video = single_path
            elif slice_path.exists():
                source_video = slice_path

        if source_video is None and selected_panels:
            if CUSTOM_VIDEO_PATH.exists():
                source_video = CUSTOM_VIDEO_PATH

        if source_video is None:
            if self.last_slice_file and self.last_slice_file.exists():
                source_video = self.last_slice_file
            else:
                if CUSTOM_VIDEO_PATH.exists():
                    source_video = CUSTOM_VIDEO_PATH
                elif OUTPUT_VIDEO_PATH.exists():
                    source_video = OUTPUT_VIDEO_PATH

        if source_video is None or not source_video.exists():
            raise FileNotFoundError("No rendered MP4 video is available yet. Please click 'Render MP4 Slice' or 'Render Custom Video Now' first.")

        shutil.copy2(source_video, target_p)
        file_size_mb = round(target_p.stat().st_size / (1024 * 1024), 2)

        return {
            "status": "success",
            "source_path": str(source_video),
            "destination_path": str(target_p),
            "file_size_mb": file_size_mb,
            "message": f"Video successfully saved to {target_p} ({file_size_mb} MB)."
        }

    def confirm_and_advance(self, panel_id: int) -> int:
        """Confirms the current panel and advances the wizard index."""
        self.completed_panels.add(panel_id)
        if panel_id < 9:
            self.current_panel = panel_id + 1
        return self.current_panel

    def set_current_panel(self, panel_id: int) -> int:
        """Navigates to a specific panel."""
        self.current_panel = max(0, min(9, panel_id))
        return self.current_panel

    def get_telemetry_baselines(self) -> dict[str, Any]:
        """Returns baseline top tracks and top artists directly extracted from Namida telemetry."""
        manifest_path = STATS_JSON_PATH
        if not manifest_path.exists():
            manifest_path = LEGACY_STATS_JSON_PATH

        tracks: list[dict[str, Any]] = []
        artists: list[dict[str, Any]] = []

        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                for t in data.get("top_tracks", [])[:5]:
                    tracks.append({
                        "rank": t.get("rank", len(tracks) + 1),
                        "title": t.get("title", ""),
                        "artist": t.get("artist", ""),
                        "plays": t.get("plays", 0),
                        "total_listen_minutes": round(t.get("total_listen_minutes", 0), 1),
                        "artwork_path": t.get("artwork_path", "")
                    })
                for a in data.get("top_artists", [])[:5]:
                    p = a.get("plays", 0)
                    a_name = a.get("artist", "")
                    artists.append({
                        "artist": a_name,
                        "plays": p,
                        "estimated_minutes": round(p * 2.8),
                        "image": self.builder.resolve_artist_avatar(a_name)
                    })
            except Exception as e:
                print(f"[Warning] Failed to load telemetry baselines: {e}")

        # Fallbacks if telemetry missing
        if not tracks:
            tracks = [
                {"rank": 1, "title": "sorry im a haunted house", "artist": "Savage Ga$p, KAMAARA", "plays": 69, "total_listen_minutes": 169.0},
                {"rank": 2, "title": "WITCHCRAFT", "artist": "AntXres, SCXR SOUL, Ethan Ross, Jupiluxe", "plays": 68, "total_listen_minutes": 167.1},
                {"rank": 3, "title": "FULL SEND RMX", "artist": "BLXCKBUSTA, Ethan Ross", "plays": 60, "total_listen_minutes": 137.9},
                {"rank": 4, "title": "BACKSTAGE", "artist": "GOTOU寄生獣, vodvor", "plays": 59, "total_listen_minutes": 106.1},
                {"rank": 5, "title": "I'll Come Runnin", "artist": "ILLENIUM, Zeds Dead, Mako", "plays": 57, "total_listen_minutes": 211.0}
            ]
        if not artists:
            raw_arts = [
                ("GOTOU寄生獣, vodvor", 510, 1428),
                ("Daegho", 193, 540),
                ("MUPP", 152, 425),
                ("Savage Ga$p", 149, 417),
                ("Kordhell, Scarlxrd", 140, 392)
            ]
            artists = [
                {
                    "artist": name,
                    "plays": plays,
                    "estimated_minutes": mins,
                    "image": self.builder.resolve_artist_avatar(name)
                }
                for name, plays, mins in raw_arts
            ]

        return {"top_tracks": tracks, "top_artists": artists}

    @staticmethod
    def extract_flac(flac_path_str: str) -> dict[str, Any]:
        """Extracts Vorbis/ID3 tags and artwork via CuratorWizard."""
        return CuratorWizard.extract_flac_metadata(flac_path_str)

    def browse_save_path(self, default_filename: str = "wrapped_2026.mp4") -> Optional[str]:
        """Opens native Windows File Explorer Save As dialog in a separate process.

        Why: Allows the user to select the destination folder and filename using the native
        OS UI rather than having to type or copy-paste file paths manually.
        """
        import subprocess
        import sys

        code = f"""
import tkinter as tk
from tkinter import filedialog
import sys

try:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    path = filedialog.asksaveasfilename(
        title='Select Save Destination',
        initialfile='{default_filename}',
        defaultextension='.mp4',
        filetypes=[('MP4 Video', '*.mp4'), ('All Files', '*.*')]
    )
    if path:
        sys.stdout.write(path)
except Exception:
    pass
"""
        try:
            import os
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            res = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=no_win,
            )
            chosen = res.stdout.strip()
            return chosen if chosen else None
        except Exception as err:
            print(f"[Dialog Error] {err}")
            return None

    def browse_audio_file(self, initial_path: Optional[str] = None) -> Optional[str]:
        """Opens native Windows File Explorer Open File dialog to pick a local audio file.

        Why: Eliminates manual path typing for song configuration across all panels and
        the slide audio mini-player.
        """
        import os
        import subprocess
        import sys

        init_dir = ""
        if initial_path and initial_path.strip():
            cand = Path(initial_path.strip(' "\''))
            if cand.is_dir():
                init_dir = str(cand)
            elif cand.parent.exists():
                init_dir = str(cand.parent)

        code = f"""
import tkinter as tk
from tkinter import filedialog
import sys

try:
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    kwargs = {{
        'title': 'Select Audio File',
        'filetypes': [
            ('Audio Files', '*.flac *.mp3 *.m4a *.wav *.aac *.ogg *.opus'),
            ('FLAC Lossless', '*.flac'),
            ('MP3 Audio', '*.mp3'),
            ('M4A / AAC Audio', '*.m4a *.aac'),
            ('WAV Audio', '*.wav'),
            ('All Files', '*.*')
        ]
    }}
    init_dir = {json.dumps(init_dir)}
    if init_dir:
        kwargs['initialdir'] = init_dir
    path = filedialog.askopenfilename(**kwargs)
    if path:
        sys.stdout.write(path)
except Exception:
    pass
"""
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            res = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=90,
                creationflags=no_win,
            )
            chosen = res.stdout.strip()
            return chosen if chosen else None
        except Exception as err:
            print(f"[Audio Dialog Error] {err}")
            return None

    def resolve_audio_stream_path(self, audio_path_str: str = "") -> tuple[Optional[Path], str]:
        """Resolves a local audio file path (or default soundtrack) and its MIME type for real-time HTTP range streaming.

        Why: Streaming the full audio track with Range support allows the browser's HTML5
        mini-player and live story preview to seek and play any 5-second window instantaneously
        without waiting for FFmpeg transcoding on every slider drag.
        """
        clean = (audio_path_str or "").strip(' "\'')
        src_p = Path(clean) if clean else DEFAULT_SOUNDTRACK_PATH
        if not src_p.is_file():
            src_p = DEFAULT_SOUNDTRACK_PATH

        if not src_p.exists() or not src_p.is_file():
            return None, "audio/aac"

        ext = src_p.suffix.lower()
        mime_map = {
            ".flac": "audio/flac",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".opus": "audio/ogg",
            ".aac": "audio/aac",
        }
        return src_p, mime_map.get(ext, "audio/mpeg")

    def generate_audio_snippet(self, audio_path_str: str, start_sec: float = 0.0) -> Optional[Path]:
        """Generates a 5.0s audio snippet with 1s fade-in and 1s fade-out for browser preview.

        Why: Allows the user to audition the exact 5-second slice transition audio right
        in the browser without rendering the entire MP4 video.
        """
        import os
        import subprocess

        src_p = Path(audio_path_str.strip(' "\''))
        if not src_p.is_file():
            src_p = DEFAULT_SOUNDTRACK_PATH

        if not src_p.exists():
            return None

        TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        safe_hash = abs(hash((str(src_p), start_sec)))
        out_clip = TEMP_AUDIO_DIR / f"preview_clip_{safe_hash}.aac"

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{max(0.0, start_sec):.2f}",
            "-t", "5.0",
            "-i", str(src_p),
            "-af", "afade=t=in:st=0:d=1,afade=t=out:st=4:d=1",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out_clip)
        ]
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=15,
                creationflags=no_win,
            )
            return out_clip if out_clip.exists() else None
        except Exception as e:
            print(f"[Warning] Audio snippet generation failed: {e}")
            return None

    async def render_isolated_slice(
        self, panel_id: int, target_path: Optional[str] = None, fps: Optional[int] = None
    ) -> Path:
        """Renders ONLY the single 5.0s clip for a specific panel.

        Why: Preview renders at 1 FPS for sub-second rapid feedback.
        Export to disk (target_path provided) renders at full 25 FPS.
        """
        import os
        import subprocess

        self.is_rendering = True
        self.render_progress = 0.0

        # Always recompile the storyboard HTML before rendering so fresh curation is reflected
        self.builder.build(output_file=STORY_HTML_PATH)
        curation = self.get_curation()
        slide_audio = curation.get("slide_audio", {})

        resolved_fps = max(1, min(60, int(fps))) if fps is not None else (25 if target_path else self.get_preview_fps())
        SLICES_DIR.mkdir(parents=True, exist_ok=True)
        slice_filename = f"wrapped_slice_single_{panel_id}.mp4"
        out_path = SLICES_DIR / slice_filename

        render_script = ROOT_DIR / "src" / "renderer" / "render_engine.js"
        soundtrack = DEFAULT_SOUNDTRACK_PATH

        node_code = f"""
const {{ renderVideo }} = require({json.dumps(str(render_script))});
renderVideo({{
  panels: [{panel_id}],
  slideAudio: {json.dumps(slide_audio)},
  fps: {resolved_fps},
  outputPath: {json.dumps(str(out_path))},
  soundtrackPath: {json.dumps(str(soundtrack))},
  storyPath: {json.dumps(str(STORY_HTML_PATH))}
}}).then(() => process.exit(0)).catch(err => {{
  console.error(err);
  process.exit(1);
}});
"""
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", node_code,
                cwd=str(ROOT_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=no_win,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"[Error] Isolated slice render failed: {stderr.decode('utf-8', errors='replace')}")
            else:
                self.last_slice_file = out_path
                if target_path:
                    import shutil
                    dest_p = Path(target_path.strip(' "\''))
                    if not dest_p.is_absolute():
                        dest_p = (ROOT_DIR / dest_p).resolve()
                    dest_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(out_path, dest_p)
        finally:
            self.is_rendering = False
            self.render_progress = 100.0

        return out_path

    async def render_custom_sequence(
        self, panel_ids: list[int], target_path: Optional[str] = None, fps: Optional[int] = None
    ) -> Path:
        """Renders an arbitrary ordered sequence of selected panel slices.

        Why: Uses configured preview FPS for studio playback preview or 25 FPS for disk export.
        """
        import os
        import subprocess

        self.is_rendering = True
        self.render_progress = 0.0

        # Always recompile the storyboard HTML before rendering so fresh curation is reflected
        self.builder.build(output_file=STORY_HTML_PATH)
        curation = self.get_curation()
        slide_audio = curation.get("slide_audio", {})

        resolved_fps = max(1, min(60, int(fps))) if fps is not None else (25 if target_path else self.get_preview_fps())
        valid_panels = [pid for pid in panel_ids if 0 <= pid <= 9]
        if not valid_panels:
            valid_panels = [0]

        RENDERS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CUSTOM_VIDEO_PATH
        render_script = ROOT_DIR / "src" / "renderer" / "render_engine.js"
        soundtrack = DEFAULT_SOUNDTRACK_PATH

        node_code = f"""
const {{ renderVideo }} = require({json.dumps(str(render_script))});
renderVideo({{
  panels: {json.dumps(valid_panels)},
  slideAudio: {json.dumps(slide_audio)},
  fps: {resolved_fps},
  outputPath: {json.dumps(str(out_path))},
  soundtrackPath: {json.dumps(str(soundtrack))},
  storyPath: {json.dumps(str(STORY_HTML_PATH))}
}}).then(() => process.exit(0)).catch(err => {{
  console.error(err);
  process.exit(1);
}});
"""
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", node_code,
                cwd=str(ROOT_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=no_win,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"[Error] Custom sequence render failed: {stderr.decode('utf-8', errors='replace')}")
            else:
                self.last_slice_file = out_path
                import shutil
                if target_path:
                    dest_p = Path(target_path.strip(' "\''))
                    if not dest_p.is_absolute():
                        dest_p = (ROOT_DIR / dest_p).resolve()
                    dest_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(out_path, dest_p)
                if valid_panels == list(range(10)):
                    shutil.copy2(out_path, OUTPUT_VIDEO_PATH)
        finally:
            self.is_rendering = False
            self.render_progress = 100.0

        return out_path

    async def render_full_video(
        self, target_path: Optional[str] = None, fps: int = 25
    ) -> Path:
        """Renders the complete 10-slide annual review story presentation at full 25 FPS (50.0s).

        Why: Produces the final pristine composite vertical video containing all 10 story bars.
        """
        import os
        import subprocess

        self.is_rendering = True
        self.render_progress = 0.0

        # Always recompile the storyboard HTML before rendering so fresh curation is reflected
        self.builder.build(output_file=STORY_HTML_PATH)
        curation = self.get_curation()
        slide_audio = curation.get("slide_audio", {})

        RENDERS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_VIDEO_PATH
        render_script = ROOT_DIR / "src" / "renderer" / "render_engine.js"
        soundtrack = DEFAULT_SOUNDTRACK_PATH

        node_code = f"""
const {{ renderVideo }} = require({json.dumps(str(render_script))});
renderVideo({{
  panels: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  slideAudio: {json.dumps(slide_audio)},
  fps: {fps},
  outputPath: {json.dumps(str(out_path))},
  soundtrackPath: {json.dumps(str(soundtrack))},
  storyPath: {json.dumps(str(STORY_HTML_PATH))}
}}).then(() => process.exit(0)).catch(err => {{
  console.error(err);
  process.exit(1);
}});
"""
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", node_code,
                cwd=str(ROOT_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=no_win,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"[Error] Full video render failed: {stderr.decode('utf-8', errors='replace')}")
            else:
                self.last_slice_file = out_path
                if target_path:
                    import shutil
                    dest_p = Path(target_path.strip(' "\''))
                    if not dest_p.is_absolute():
                        dest_p = (ROOT_DIR / dest_p).resolve()
                    dest_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(out_path, dest_p)
        finally:
            self.is_rendering = False
            self.render_progress = 100.0

        return out_path

    async def render_video_slice(self, up_to_panel: int, fps: Optional[int] = None) -> Path:
        """Asynchronously renders an MP4 video slice preview up to the specified panel at the configured preview FPS.

        Why: Allows rapid visual inspection at the user-configured preview framerate.
        """
        import os
        import subprocess

        self.is_rendering = True
        self.render_progress = 0.0

        # Always recompile the storyboard HTML before rendering so fresh curation is reflected
        self.builder.build(output_file=STORY_HTML_PATH)
        curation = self.get_curation()
        slide_audio = curation.get("slide_audio", {})
        resolved_fps = max(1, min(60, int(fps))) if fps is not None else self.get_preview_fps()

        SLICES_DIR.mkdir(parents=True, exist_ok=True)
        slice_filename = f"wrapped_slice_panel_{up_to_panel}.mp4"
        out_path = SLICES_DIR / slice_filename

        render_script = ROOT_DIR / "src" / "renderer" / "render_engine.js"
        soundtrack = DEFAULT_SOUNDTRACK_PATH

        panels_list = list(range(up_to_panel + 1))
        node_code = f"""
const {{ renderVideo }} = require({json.dumps(str(render_script))});
renderVideo({{
  panels: {json.dumps(panels_list)},
  slideAudio: {json.dumps(slide_audio)},
  fps: {resolved_fps},
  outputPath: {json.dumps(str(out_path))},
  soundtrackPath: {json.dumps(str(soundtrack))},
  storyPath: {json.dumps(str(STORY_HTML_PATH))}
}}).then(() => process.exit(0)).catch(err => {{
  console.error(err);
  process.exit(1);
}});
"""
        try:
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", node_code,
                cwd=str(ROOT_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=no_win,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                print(f"[Error] Slice render failed: {stderr.decode('utf-8', errors='replace')}")
            else:
                self.last_slice_file = out_path
        finally:
            self.is_rendering = False
            self.render_progress = 100.0

        return out_path



# Global singleton service instance
studio_service = StudioService()

