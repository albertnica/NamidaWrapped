"""
Interactive CLI Curator & Local FLAC Metadata Extractor.
Allows the user to merge Spotify telemetry and manually curate Top Songs, Albums, Artists, Discoveries, and Genres.
Author: Antigravity
Python: 3.13.12
"""

import base64
import json
from pathlib import Path
from typing import Any
import urllib.request

try:
    import mutagen
    import mutagen.flac
except ImportError:
    mutagen = None

from src.config import CURATION_JSON_PATH, CURRENT_YEAR, DEFAULT_SOUNDTRACK_PATH, OUTPUT_DIR, ROOT_DIR


class CuratorWizard:
    """Manages interactive user curation and local audio file metadata extraction.

    Why: Ground-truth music appreciation is often emotional and cross-platform
    (Namida lossless library + Spotify desktop/workday), requiring hybrid input
    rather than purely raw automated device logs.
    """

    def __init__(self, curation_path: Path = CURATION_JSON_PATH):
        self.curation_path = Path(curation_path)
        self.curation_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def extract_flac_metadata(flac_path_str: str) -> dict[str, Any]:
        """Extracts Vorbis/ID3/MP4 tags, duration, and embedded cover artwork from local audio files.

        Why: Eliminates manual copy-pasting of song/album names and renders original
        album artwork embedded directly inside the user's FLAC, MP3, or M4A audio files.
        """
        clean_str = (flac_path_str or "").strip(' "\'')
        p = Path(clean_str) if clean_str else DEFAULT_SOUNDTRACK_PATH
        if not p.exists() or not p.is_file():
            stem = p.stem or "Track"
            return {
                "path": str(p),
                "title": stem,
                "artist": "Curated Selection",
                "album": stem,
                "artwork": "",
                "duration": 0.0,
                "valid": False,
            }

        is_default_soundtrack = (p.name == "soundtrack.aac")
        title = "Default Soundtrack" if is_default_soundtrack else p.stem
        artist = "2026 Wrapped" if is_default_soundtrack else "Unknown Artist"
        album = p.stem
        artwork_b64 = ""
        duration_sec = 0.0

        try:
            if mutagen:
                audio = None
                if p.suffix.lower() == ".flac":
                    try:
                        audio = mutagen.flac.FLAC(str(p))
                    except Exception:
                        pass
                if audio is None:
                    audio = mutagen.File(str(p))

                if audio:
                    if hasattr(audio, "info") and getattr(audio.info, "length", None):
                        try:
                            duration_sec = round(float(audio.info.length), 2)
                        except Exception:
                            pass

                    # Extract title
                    for k in ["title", "TIT2", "\xa9nam"]:
                        if k in audio:
                            val = audio[k]
                            title = str(val[0] if isinstance(val, (list, tuple)) else val)
                            break

                    # Extract artist
                    for k in ["artist", "TPE1", "\xa9ART"]:
                        if k in audio:
                            val = audio[k]
                            artist = str(val[0] if isinstance(val, (list, tuple)) else val)
                            break

                    # Extract album
                    for k in ["album", "TALB", "\xa9alb"]:
                        if k in audio:
                            val = audio[k]
                            album = str(val[0] if isinstance(val, (list, tuple)) else val)
                            break

                    # Extract embedded front cover artwork
                    # 1. FLAC pictures
                    if hasattr(audio, "pictures") and len(audio.pictures) > 0:
                        pic = audio.pictures[0]
                        mime = getattr(pic, "mime", "image/jpeg")
                        data = getattr(pic, "data", b"")
                        if data:
                            artwork_b64 = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

                    # 2. ID3 APIC frames
                    if not artwork_b64 and hasattr(audio, "tags") and audio.tags:
                        for tag_name, tag_val in audio.tags.items():
                            if tag_name.startswith("APIC"):
                                mime = getattr(tag_val, "mime", "image/jpeg")
                                data = getattr(tag_val, "data", b"")
                                if data:
                                    artwork_b64 = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
                                    break
                            elif tag_name == "covr" and isinstance(tag_val, list) and len(tag_val) > 0:
                                cdata = bytes(tag_val[0])
                                mime = "image/png" if cdata.startswith(b"\x89PNG") else "image/jpeg"
                                artwork_b64 = f"data:{mime};base64,{base64.b64encode(cdata).decode('ascii')}"
                                break
        except Exception as e:
            print(f"      [Warning] Could not extract mutagen tags from {p.name}: {e}")

        # Check folder cover if embedded artwork missing
        if not artwork_b64:
            for cover_name in ("cover.jpg", "cover.png", "folder.jpg", "front.jpg"):
                cover_p = p.parent / cover_name
                if cover_p.exists():
                    try:
                        c_mime = "image/png" if cover_p.suffix.lower() == ".png" else "image/jpeg"
                        c_data = cover_p.read_bytes()
                        artwork_b64 = f"data:{c_mime};base64,{base64.b64encode(c_data).decode('ascii')}"
                        break
                    except Exception:
                        pass

        # Fallback to ffprobe for duration if mutagen did not report length (e.g., raw AAC ADTS)
        if duration_sec <= 0.0:
            try:
                import os
                import subprocess
                no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
                res = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        str(p)
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=no_win,
                )
                if res.returncode == 0 and res.stdout.strip():
                    duration_sec = round(float(res.stdout.strip()), 2)
            except Exception:
                pass

        return {
            "path": str(p),
            "title": title,
            "artist": artist,
            "album": album,
            "artwork": artwork_b64,
            "duration": duration_sec,
            "valid": True,
        }

    @staticmethod
    def resolve_image_url_or_path(img_src: str) -> str:
        """Resolves local image path or remote image URL into base64 or safe web URL.

        Why: Ensures offline headless Chromium can render local filesystem avatars
        or downloaded artist portraits without broken CORS/file scheme blocks.
        """
        if not img_src or not img_src.strip():
            return ""

        s = img_src.strip(' "\'')
        if s.startswith("data:image"):
            return s

        local_p = Path(s)
        if local_p.exists() and local_p.is_file():
            try:
                mime = "image/png" if local_p.suffix.lower() == ".png" else "image/jpeg"
                data = local_p.read_bytes()
                return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
            except Exception:
                pass

        if s.startswith("http://") or s.startswith("https://"):
            try:
                req = urllib.request.Request(s, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    c_type = resp.headers.get_content_type() or "image/jpeg"
                    data = resp.read()
                    return f"data:{c_type};base64,{base64.b64encode(data).decode('ascii')}"
            except Exception:
                return s

        return s

    def load_curation_data(self) -> dict[str, Any]:
        """Loads existing curation manifest or generates standard production defaults.

        Why: Ensures generation and video rendering pipelines remain deterministic
        and never crash even if the user has not yet executed the interactive CLI wizard.
        """
        if self.curation_path.exists():
            try:
                return json.loads(self.curation_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Production defaults reflecting authentic curated baseline
        return {
            "spotify_additions": {
                "extra_minutes": 14200,
                "extra_plays": 3850,
                "extra_songs": 640,
                "extra_streak": 0,
            },
            "listening_clock": {
                "work_hours_minutes_total": 8500,
                "saturday_extra_minutes": 1450,
            },
            "top_songs": [
                {
                    "title": "sorry im a haunted house",
                    "artist": "Savage Ga$p, KAMAARA",
                    "path": "",
                    "artwork": "",
                },
                {
                    "title": "WITCHCRAFT",
                    "artist": "AntXres, SCXR SOUL, Ethan Ross, Jupiluxe",
                    "path": "",
                    "artwork": "",
                },
                {
                    "title": "FULL SEND RMX",
                    "artist": "BLXCKBUSTA, Ethan Ross",
                    "path": "",
                    "artwork": "",
                },
                {
                    "title": "BACKSTAGE",
                    "artist": "GOTOU寄生獣, vodvor",
                    "path": "",
                    "artwork": "",
                },
                {
                    "title": "I'll Come Runnin",
                    "artist": "ILLENIUM, Zeds Dead, Mako",
                    "path": "",
                    "artwork": "",
                },
            ],
            "top_albums": [
                {
                    "album": "sorry im a haunted house",
                    "artist": "Savage Ga$p",
                    "artwork": "",
                },
                {
                    "album": "FALLEN ANGEL",
                    "artist": "ILLENIUM",
                    "artwork": "",
                },
                {
                    "album": "SCXR ARCHIVES",
                    "artist": "SCXR SOUL",
                    "artwork": "",
                },
                {
                    "album": "PHONK NATION",
                    "artist": "Various Artists",
                    "artwork": "",
                },
                {
                    "album": "ASCEND",
                    "artist": "ILLENIUM",
                    "artwork": "",
                },
            ],
            "top_artists": [
                {"name": "ILLENIUM", "image": ""},
                {"name": "Savage Ga$p", "image": ""},
                {"name": "SCXR SOUL", "image": ""},
                {"name": "Ethan Ross", "image": ""},
                {"name": "KAMAARA", "image": ""},
            ],
            "top_discoveries": [
                {"name": "GOTOU寄生獣", "image": ""},
                {"name": "AntXres", "image": ""},
                {"name": "vodvor", "image": ""},
                {"name": "BLXCKBUSTA", "image": ""},
                {"name": "Zeds Dead", "image": ""},
            ],
            "top_genres": [
                {"genre": "Phonk", "song": "WITCHCRAFT"},
                {"genre": "Melodic Bass", "song": "I'll Come Runnin"},
                {"genre": "Trap Metal", "song": "sorry im a haunted house"},
                {"genre": "Drift Phonk", "song": "FULL SEND RMX"},
                {"genre": "Future Bass", "song": "Nightlight"},
            ],
        }

    def save_curation_data(self, data: dict[str, Any]) -> Path:
        """Writes verified curation data to JSON on disk."""
        self.curation_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n[SUCCESS] Curation manifest saved to: {self.curation_path}")
        return self.curation_path

    def run_interactive_wizard(self) -> dict[str, Any]:
        """Runs the complete interactive command-line questionnaire.

        Why: Guides the user through merging their Spotify telemetry and setting
        their curated Top Songs, Albums, Artists, Discoveries, and Genres.
        """
        current = self.load_curation_data()

        print("\n" + "=" * 65)
        print("   2026 WRAPPED: INTERACTIVE CURATION & TELEMETRY WIZARD")
        print("=" * 65)
        print("Press ENTER to keep the current/default value shown in [brackets].\n")

        # -------------------------------------------------------------
        # 1. Spotify Additional Stats
        # -------------------------------------------------------------
        print("--- [1/7] SPOTIFY ADDITIONAL TELEMETRY ---")
        sp = current.get("spotify_additions", {})

        def prompt_int(msg: str, default_val: int) -> int:
            val_str = input(f"  • {msg} [{default_val:,}]: ").strip()
            if not val_str:
                return default_val
            try:
                return int(val_str.replace(",", ""))
            except ValueError:
                return default_val

        sp["extra_minutes"] = prompt_int("Additional listening minutes (Spotify)", sp.get("extra_minutes", 14200))
        sp["extra_plays"] = prompt_int("Additional total tracks played", sp.get("extra_plays", 3850))
        sp["extra_songs"] = prompt_int("Additional unique tracks listened", sp.get("extra_songs", 640))
        current["spotify_additions"] = sp

        # -------------------------------------------------------------
        # 2. Listening Clock Telemetry Adjustments
        # -------------------------------------------------------------
        print("\n--- [2/7] LISTENING CLOCK & WORKING HOURS ---")
        clock = current.get("listening_clock", {})
        clock["work_hours_minutes_total"] = prompt_int(
            "Additional minutes between 7 AM and 3 PM (Spotify work hours)",
            clock.get("work_hours_minutes_total", 8500),
        )
        clock["saturday_extra_minutes"] = prompt_int(
            "Additional minutes for Saturdays (weekly releases)",
            clock.get("saturday_extra_minutes", 1450),
        )
        current["listening_clock"] = clock

        # -------------------------------------------------------------
        # 3. Top Songs (Curated Local FLAC Files)
        # -------------------------------------------------------------
        print("\n--- [3/7] TOP 5 SONGS (Local FLAC Paths) ---")
        print("  (Enter the path to your local FLAC files. Title, artist, and cover art will be extracted automatically)")
        top_songs = current.get("top_songs", [])
        updated_songs = []
        for i in range(1, 6):
            existing = top_songs[i - 1] if len(top_songs) >= i else {}
            curr_path = existing.get("path", "")
            curr_title = existing.get("title", f"Track #{i}")
            curr_artist = existing.get("artist", "")

            user_p = input(f"  • Top {i} FLAC path [{curr_path or f'{curr_title} - {curr_artist}'}]: ").strip()
            target_path = user_p if user_p else curr_path

            if target_path and Path(target_path.strip(' "\'')).exists():
                meta = self.extract_flac_metadata(target_path)
                print(f"      ✓ Detected: \"{meta['title']}\" by {meta['artist']}")
                updated_songs.append({
                    "title": meta["title"],
                    "artist": meta["artist"],
                    "path": meta["path"],
                    "artwork": meta["artwork"] or existing.get("artwork", ""),
                })
            else:
                # Keep manual or existing title/artist
                t_input = input(f"      Title [{curr_title}]: ").strip() or curr_title
                a_input = input(f"      Artist [{curr_artist}]: ").strip() or curr_artist
                updated_songs.append({
                    "title": t_input,
                    "artist": a_input,
                    "path": target_path,
                    "artwork": existing.get("artwork", ""),
                })
        current["top_songs"] = updated_songs

        # -------------------------------------------------------------
        # 4. Top Albums (Curated Local FLAC Files or Names)
        # -------------------------------------------------------------
        print("\n--- [4/7] TOP 5 ALBUMS ---")
        top_albums = current.get("top_albums", [])
        updated_albums = []
        for i in range(1, 6):
            existing = top_albums[i - 1] if len(top_albums) >= i else {}
            curr_album = existing.get("album", f"Album #{i}")
            curr_artist = existing.get("artist", "")
            curr_path = existing.get("path", "")

            user_p = input(f"  • Top {i} Album FLAC path or Album Name [{curr_path or curr_album}]: ").strip()
            target_path = user_p if user_p else (curr_path or curr_album)

            if target_path and Path(target_path.strip(' "\'')).exists():
                meta = self.extract_flac_metadata(target_path)
                print(f"      ✓ Detected Album: \"{meta['album']}\" by {meta['artist']}")
                updated_albums.append({
                    "album": meta["album"],
                    "artist": meta["artist"],
                    "path": meta["path"],
                    "artwork": meta["artwork"] or existing.get("artwork", ""),
                })
            else:
                alb_name = target_path if (target_path and not Path(target_path).exists()) else curr_album
                alb_artist = input(f"      Album Artist [{curr_artist}]: ").strip() or curr_artist
                updated_albums.append({
                    "album": alb_name,
                    "artist": alb_artist,
                    "path": "",
                    "artwork": existing.get("artwork", ""),
                })
        current["top_albums"] = updated_albums

        # -------------------------------------------------------------
        # 5. Top Artists
        # -------------------------------------------------------------
        print("\n--- [5/7] TOP 5 ARTISTS ---")
        top_artists = current.get("top_artists", [])
        updated_artists = []
        for i in range(1, 6):
            existing = top_artists[i - 1] if len(top_artists) >= i else {}
            curr_name = existing.get("name", "ILLENIUM" if i == 1 else f"Artist #{i}")
            curr_img = existing.get("image", "")

            name_in = input(f"  • Top {i} Artist Name [{curr_name}]: ").strip() or curr_name
            img_in = input(f"      Image Path/URL for {name_in} (optional) [{curr_img[:30]}...]: ").strip()
            resolved_img = self.resolve_image_url_or_path(img_in) if img_in else curr_img

            updated_artists.append({"name": name_in, "image": resolved_img})
        current["top_artists"] = updated_artists

        # -------------------------------------------------------------
        # 6. Top Discoveries
        # -------------------------------------------------------------
        print("\n--- [6/7] TOP 5 DISCOVERIES (Artists discovered this year) ---")
        top_disc = current.get("top_discoveries", [])
        updated_disc = []
        for i in range(1, 6):
            existing = top_disc[i - 1] if len(top_disc) >= i else {}
            curr_name = existing.get("name", f"Discovery #{i}")
            curr_img = existing.get("image", "")

            name_in = input(f"  • Discovery {i} Artist Name [{curr_name}]: ").strip() or curr_name
            img_in = input(f"      Image Path/URL for {name_in} (optional) [{curr_img[:30]}...]: ").strip()
            resolved_img = self.resolve_image_url_or_path(img_in) if img_in else curr_img

            updated_disc.append({"name": name_in, "image": resolved_img})
        current["top_discoveries"] = updated_disc

        # -------------------------------------------------------------
        # 7. Top Genres & Representative Songs
        # -------------------------------------------------------------
        print("\n--- [7/7] TOP GENRES & REPRESENTATIVE SONGS ---")
        top_genres = current.get("top_genres", [])
        updated_genres = []
        for i in range(1, 6):
            existing = top_genres[i - 1] if len(top_genres) >= i else {}
            curr_genre = existing.get("genre", f"Genre #{i}")
            curr_song = existing.get("song", "Representative Track")

            genre_in = input(f"  • Top {i} Genre Name [{curr_genre}]: ").strip() or curr_genre
            song_in = input(f"      Representative song for {genre_in} [{curr_song}]: ").strip() or curr_song

            updated_genres.append({"genre": genre_in, "song": song_in})
        current["top_genres"] = updated_genres

        # Save and return
        self.save_curation_data(current)
        return current
