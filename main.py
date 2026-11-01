"""
Unified Command-Line Interface for 2026 Wrapped Pipeline.
Modular execution for data analysis, HTML5 storyboard generation, preview capture, and MP4 rendering.
Author: Antigravity
Python: 3.13.12
"""

import argparse
from pathlib import Path
import subprocess
import sys
from typing import NoReturn

from src.analyzer.extractor import BackupExtractor
from src.analyzer.normalizer import TrackResolver
from src.analyzer.stats import TelemetryStatsEngine
from src.config import (
    CURRENT_YEAR,
    DEFAULT_BACKUP_PATH,
    LOGS_DIR,
    OUTPUT_DIR,
    ROOT_DIR,
    SERVER_LOG_PATH,
    STATS_JSON_PATH,
    STORY_HTML_PATH,
)
from src.templates.builder import StoryboardBuilder


def run_analyze(archive_path: Path, target_year: int) -> dict:
    """Extracts raw telemetry from backup archive and generates canonical stats JSON.

    Why: Separates raw archive decompression and data normalization from rendering.
    """
    print(f"\n[1/3] Initializing Data Extraction from: {archive_path.name}")
    extractor = BackupExtractor(archive_path)

    print("[2/3] Parsing SQLite database and building normalization indices...")
    raw_tracks = extractor.read_tracks_database()
    resolver = TrackResolver(raw_tracks)

    print(f"[3/3] Aggregating telemetry logs for year {target_year}...")
    engine = TelemetryStatsEngine(extractor, resolver, target_year=target_year)
    manifest = engine.aggregate(OUTPUT_DIR)

    headline = manifest["headline_metrics"]
    print(f"\n=== Aggregation Results ({target_year}) ===")
    print(f"  • Total Listen Time   : {headline['total_listen_minutes']:,} min ({headline['total_listen_hours']:,} hrs)")
    print(f"  • Total Plays         : {headline['total_plays']:,}")
    print(f"  • Unique Tracks       : {headline['unique_tracks']:,} ({headline['unique_artists']:,} artists)")
    print(f"  • Active Days         : {headline['active_days']} (Max Streak: {headline['listening_streak_days']} days)")
    print(f"  • Lossless Audio      : {headline['lossless_percentage']}% FLAC")
    print(f"  • Manifest Saved To   : {STATS_JSON_PATH}")
    return manifest


def run_generate(target_year: int) -> Path:
    """Builds the full-bleed HTML5 storyboard combining templates, assets, and metrics.

    Why: Produces an offline, self-contained DOM that headless Chrome can seek deterministically.
    """
    print(f"\n[1/1] Compiling HTML5 Storyboard for {target_year} Wrapped...")
    builder = StoryboardBuilder(target_year=target_year)
    out_html = builder.build(output_file=STORY_HTML_PATH)
    print(f"[SUCCESS] Storyboard compiled at: {out_html}")
    return out_html


def run_preview() -> None:
    """Runs headless Chrome to capture static test screenshots of each slide.

    Why: Allows rapid visual verification without encoding all 712 frames of MP4.
    """
    print("\n[Preview Engine] Capturing keyframe screenshots for visual validation...")
    preview_script = ROOT_DIR / "src" / "renderer" / "preview_engine.js"
    cmd = ["node", str(preview_script)]
    subprocess.run(cmd, check=True)


def run_render() -> None:
    """Executes Puppeteer and FFmpeg to render the final vertical MP4 video.

    Why: Headless frame-by-frame streaming guarantees smooth 25 FPS without dropped frames.
    """
    print("\n[Video Engine] Initiating video render stream...")
    render_script = ROOT_DIR / "src" / "renderer" / "render_engine.js"
    cmd = ["node", str(render_script)]
    subprocess.run(cmd, check=True)


def run_configure() -> dict:
    """Executes the interactive command-line curation wizard for user overrides and Spotify data.

    Why: Allows the user to provide cross-platform listening numbers and curated favorites.
    """
    from src.curator.wizard import CuratorWizard
    wizard = CuratorWizard()
    return wizard.run_interactive_wizard()


def free_port(port: int) -> None:
    """Finds and forcefully terminates any process currently bound to target port.

    Why: Prevents [Errno 10048] socket binding failures when launching Web Studio.
    """
    import os
    import signal
    import subprocess

    try:
        if os.name == "nt":
            no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
            output = subprocess.check_output(
                cmd, shell=True, text=True, stderr=subprocess.DEVNULL, creationflags=no_win
            )
            pids = set()
            current_pid = os.getpid()
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and f":{port}" in parts[1]:
                    try:
                        pid = int(parts[-1])
                        if pid != current_pid and pid > 0:
                            pids.add(pid)
                    except ValueError:
                        pass
            for pid in pids:
                print(f"[Web Studio] Port {port} is occupied by PID {pid}. Terminating process {pid}...")
                subprocess.run(
                    f"taskkill /F /PID {pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=no_win,
                )
        else:
            cmd = f"lsof -t -i:{port}"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            current_pid = os.getpid()
            for line in output.strip().splitlines():
                try:
                    pid = int(line)
                    if pid != current_pid:
                        print(f"[Web Studio] Port {port} is occupied by PID {pid}. Terminating process {pid}...")
                        os.kill(pid, signal.SIGKILL)
                except ValueError:
                    pass
    except Exception:
        pass


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
    """Polls TCP socket until the background Uvicorn server is accepting connections.

    Why: Ensures the browser opens only after FastAPI is ready to serve requests.
    """
    import socket
    import time

    deadline = time.monotonic() + timeout
    check_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((check_host, port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.12)
    return False


def _close_parent_shell_if_interactive() -> None:
    """Closes the parent PowerShell/CMD console window if launched interactively.

    Why: Frees the user from keeping a terminal window open while Web Studio runs in the background.
    """
    import os

    if os.name != "nt":
        return
    try:
        if not (sys.stdin and sys.stdin.isatty()):
            return
        ppid = os.getppid()
        if ppid <= 0 or ppid == os.getpid():
            return
        no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # Check parent process executable name
        out = subprocess.check_output(
            f'tasklist /FI "PID eq {ppid}" /FO CSV /NH',
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=no_win,
        ).lower()
        if any(shell_name in out for shell_name in ("powershell.exe", "pwsh.exe", "cmd.exe")):
            subprocess.Popen(
                f"taskkill /PID {ppid} /F",
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=no_win | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
    except Exception:
        pass


def run_studio(
    host: str = "127.0.0.1",
    port: int = 8000,
    foreground: bool = False,
    keep_shell: bool = False,
) -> None:
    """Launches the interactive Web Studio curation service.

    Why: By default, spawns Uvicorn as a windowless background daemon, opens the browser
    once ready, and closes the parent PowerShell window so no terminal remains open.
    Note: On Windows, CREATE_NO_WINDOW must NOT be combined with DETACHED_PROCESS because
    Win32 CreateProcess ignores CREATE_NO_WINDOW when DETACHED_PROCESS is set, causing
    child console processes (ffprobe, ffmpeg, node) to flash visible console windows.
    """
    import os
    import webbrowser

    url = f"http://{host}:{port}"

    if not foreground:
        free_port(port)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = SERVER_LOG_PATH
        log_file = open(log_path, "a", encoding="utf-8")

        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "studio",
            "--host",
            host,
            "--port",
            str(port),
            "--foreground",
        ]

        popen_kwargs: dict = {
            "cwd": str(ROOT_DIR),
            "stdin": subprocess.DEVNULL,
            "stdout": log_file,
            "stderr": log_file,
            "close_fds": True,
        }
        if os.name == "nt":
            base_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            breakaway_flag = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
            try:
                popen_kwargs["creationflags"] = base_flags | breakaway_flag
                proc = subprocess.Popen(cmd, **popen_kwargs)
            except OSError:
                popen_kwargs["creationflags"] = base_flags
                proc = subprocess.Popen(cmd, **popen_kwargs)
        else:
            popen_kwargs["start_new_session"] = True
            proc = subprocess.Popen(cmd, **popen_kwargs)
        print(f"\n[Web Studio] Starting background server (PID {proc.pid}) on {url} ...")

        ready = _wait_for_port(host, port, timeout=6.0)
        if ready:
            print(f"[Web Studio] Server ready at {url} (logs: {log_path})")
            if not os.environ.get("NAMIDA_NO_BROWSER"):
                webbrowser.open(url)
            if not keep_shell:
                _close_parent_shell_if_interactive()
        else:
            print(
                f"[Web Studio] Warning: Server did not respond within 6s. Check {log_path}",
                file=sys.stderr,
            )
        return

    import uvicorn

    if sys.platform == "win32":
        try:
            from asyncio.proactor_events import _ProactorBasePipeTransport
            _orig_call_conn_lost = _ProactorBasePipeTransport._call_connection_lost

            def _safe_call_conn_lost(self, exc):
                try:
                    _orig_call_conn_lost(self, exc)
                except (ConnectionResetError, ConnectionAbortedError, OSError):
                    pass

            _ProactorBasePipeTransport._call_connection_lost = _safe_call_conn_lost
        except Exception:
            pass

    uvicorn.run("src.server.app:app", host=host, port=port, log_level="info", reload=False)


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="2026 Wrapped Pipeline: Analytical Extraction, Storyboard Generation, and Video Rendering"
    )
    # UI flag and shared network parameters
    parser.add_argument("--ui", action="store_true", help="Launch interactive browser studio in background")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address for studio UI")
    parser.add_argument("--port", type=int, default=8000, help="Port number for studio UI")
    parser.add_argument("--foreground", action="store_true", help="Run studio server attached to current terminal")
    parser.add_argument("--keep-shell", action="store_true", help="Do not auto-close PowerShell after launching background server")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: studio
    p_studio = subparsers.add_parser("studio", help="Launch interactive browser studio (detached background daemon by default)")
    p_studio.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    p_studio.add_argument("--port", type=int, default=8000, help="Port number")
    p_studio.add_argument("--foreground", action="store_true", help="Run studio server attached to current terminal")
    p_studio.add_argument("--keep-shell", action="store_true", help="Do not auto-close PowerShell after launching background server")

    # Command: setup
    subparsers.add_parser("setup", help="Run interactive environment & prerequisite diagnostics wizard")

    # Command: configure
    subparsers.add_parser("configure", help="Launch interactive CLI wizard for Spotify additions & curated selections")

    # Command: analyze
    p_analyze = subparsers.add_parser("analyze", help="Extract and aggregate data from backup archive")
    p_analyze.add_argument("--archive", type=Path, default=DEFAULT_BACKUP_PATH, help="Path to backup ZIP")
    p_analyze.add_argument("--year", type=int, default=CURRENT_YEAR, help="Target statistics year")

    # Command: generate
    p_generate = subparsers.add_parser("generate", help="Compile HTML5 storyboard from templates and stats")
    p_generate.add_argument("--year", type=int, default=CURRENT_YEAR, help="Target year")

    # Command: preview
    subparsers.add_parser("preview", help="Capture slide previews via headless Chrome")

    # Command: render
    subparsers.add_parser("render", help="Render full 1080x1920 MP4 video with FFmpeg")

    # Command: all
    p_all = subparsers.add_parser("all", help="Execute complete pipeline: analyze -> generate -> render")
    p_all.add_argument("--archive", type=Path, default=DEFAULT_BACKUP_PATH, help="Path to backup ZIP")
    p_all.add_argument("--year", type=int, default=CURRENT_YEAR, help="Target statistics year")

    args = parser.parse_args()

    if args.ui or args.command == "studio":
        try:
            run_studio(
                host=args.host,
                port=args.port,
                foreground=getattr(args, "foreground", False),
                keep_shell=getattr(args, "keep_shell", False),
            )
        except Exception as exc:
            print(f"\n[FATAL ERROR] {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "setup":
            from src.setup_wizard import main as run_setup_wizard
            run_setup_wizard()
        elif args.command == "configure":
            run_configure()
        elif args.command == "analyze":
            run_analyze(args.archive, args.year)
        elif args.command == "generate":
            run_generate(args.year)
        elif args.command == "preview":
            run_preview()
        elif args.command == "render":
            run_render()
        elif args.command == "all":
            run_analyze(args.archive, args.year)
            run_generate(args.year)
            run_render()
    except Exception as exc:
        print(f"\n[FATAL ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
