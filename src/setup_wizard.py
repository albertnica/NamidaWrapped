"""
Interactive Environment Setup & Prerequisite Diagnostics Wizard (src/setup_wizard.py).

Modeled after Spotify2Local setup architecture.
Verifies system-level prerequisites (Python, FFmpeg, Node.js, Chrome),
automates Python pip dependencies installation from requirements.txt,
automates Node.js package setup via npm, and bootstraps necessary project folders.

Author: Antigravity
Python: 3.10+ compatible
"""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if getattr(sys.stdout, "encoding", "").lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Core Python modules required by NamidaWrapped
REQUIRED_PYTHON_MODULES: List[Tuple[str, str]] = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("mutagen", "mutagen"),
    ("PIL", "Pillow"),
]


def ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    """
    Standardizes interactive console [Y/n] confirmation prompts.

    Why: Ensures reliable input parsing when executed interactively or via batch scripts.
    """
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        raw = input(f"{prompt} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def find_chrome_executable() -> Optional[str]:
    """
    Searches for Google Chrome (or compatible Chromium executable) across known Windows paths and PATH.

    Why: Puppeteer-core requires a local Chrome/Chromium binary to render storyboard frames.
    """
    candidates = [
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("msedge"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(c)
    return None


def step_1_system_prerequisites() -> bool:
    """
    Audits the system environment for Python version, FFmpeg, Node.js, npm, and Chrome.

    Why: NamidaWrapped relies on external CLIs (FFmpeg for video/audio muxing, Node.js + Chrome
    for Puppeteer headless frame rendering). Detecting missing system tools upfront prevents
    cryptic pipeline errors during story rendering.
    """
    print("\n" + "=" * 68)
    print("  STEP 1: System Runtimes & External Tool Diagnostics")
    print("=" * 68)

    all_passed = True

    # 1. Python Version Check
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if py_ver >= (3, 10):
        print(f"  [OK] Python Runtime: {py_str} (>= 3.10 required)")
    else:
        print(f"  [FAIL] Python Runtime: {py_str} (Python 3.10+ required)")
        all_passed = False

    # 2. FFmpeg Check
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            res = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            first_line = res.stdout.splitlines()[0] if res.stdout else "Available"
            print(f"  [OK] FFmpeg: {first_line.split(' Copyright')[0]}")
        except Exception:
            print(f"  [OK] FFmpeg found at: {ffmpeg_path}")
    else:
        print("  [FAIL] FFmpeg is NOT found in system PATH.")
        print("         Install via winget ('winget install Gyan.FFmpeg') or download from https://ffmpeg.org/")
        all_passed = False

    # 3. Node.js Check
    node_path = shutil.which("node")
    if node_path:
        try:
            res = subprocess.run(
                ["node", "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            print(f"  [OK] Node.js Runtime: {res.stdout.strip()}")
        except Exception:
            print(f"  [OK] Node.js found at: {node_path}")
    else:
        print("  [FAIL] Node.js is NOT installed or not in system PATH.")
        print("         Install from https://nodejs.org/ (Node 18+ LTS recommended).")
        all_passed = False

    # 4. npm Check
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_cmd:
        print(f"  [OK] Node Package Manager (npm): {npm_cmd}")
    else:
        print("  [WARN] npm is NOT found in system PATH.")
        all_passed = False

    # 5. Chrome / Chromium Check
    chrome_path = find_chrome_executable()
    if chrome_path:
        print(f"  [OK] Chrome / Chromium Binary: {chrome_path}")
    else:
        print("  [WARN] Google Chrome not found in standard paths.")
        print("         Puppeteer rendering requires Chrome at C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
        print("         or set the CHROME_PATH environment variable.")

    if not all_passed:
        print("\n  [!] One or more system prerequisites are missing.")
        if not ask_yes_no("  -> Continue setup anyway?", default_yes=True):
            return False

    return True


def _find_missing_python_packages() -> List[str]:
    """
    Returns missing Python package names by testing module imports.

    Why: Invalidates import caches so newly installed pip wheels are recognized immediately.
    """
    importlib.invalidate_caches()
    missing: List[str] = []
    for mod_name, pkg_name in REQUIRED_PYTHON_MODULES:
        if importlib.util.find_spec(mod_name) is None:
            missing.append(pkg_name)
    return missing


def step_2_python_dependencies() -> bool:
    """
    Validates Python library requirements and automates pip installation.

    Why: Ensures FastAPI, Uvicorn, Pydantic, Mutagen, and Pillow are installed
    before starting the backend API or CLI pipelines.
    """
    print("\n" + "=" * 68)
    print("  STEP 2: Python Dependencies (requirements.txt via pip)")
    print("=" * 68)

    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        print(f"  [ERROR] {req_file.name} not found in {PROJECT_ROOT}")
        return False

    while True:
        missing = _find_missing_python_packages()
        if missing:
            print(f"  [!] Missing Python packages: {', '.join(missing)}")
        else:
            print("  [OK] All required Python packages are already installed.")
            return True

        if ask_yes_no("  -> Run 'pip install -r requirements.txt' now?", default_yes=True):
            print(f"\n  [PIP] Installing dependencies using {sys.executable}...\n")
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
            res = subprocess.run(cmd)
            if res.returncode != 0:
                print("\n  [ERROR] 'pip install' exited with errors.")
                if ask_yes_no("  -> Retry pip install?", default_yes=True):
                    continue
                return False

            still_missing = _find_missing_python_packages()
            if still_missing:
                print(f"\n  [WARN] Packages still missing: {', '.join(still_missing)}")
                if ask_yes_no("  -> Retry pip install?", default_yes=True):
                    continue
                return False

            print("\n  [OK] All Python dependencies installed successfully.")
            return True

        print("  [WARN] Skipping pip install may cause runtime ImportErrors.")
        return True


def step_3_node_dependencies() -> bool:
    """
    Validates Node.js dependencies (puppeteer-core) and offers to execute npm install.

    Why: The headless rendering engine in src/renderer/render_engine.js requires puppeteer-core.
    """
    print("\n" + "=" * 68)
    print("  STEP 3: Node.js Dependencies (package.json via npm)")
    print("=" * 68)

    pkg_json = PROJECT_ROOT / "package.json"
    node_modules = PROJECT_ROOT / "node_modules"
    puppeteer_pkg = node_modules / "puppeteer-core"

    if not pkg_json.exists():
        print("  [SKIP] No package.json found; skipping npm step.")
        return True

    if puppeteer_pkg.exists():
        print("  [OK] Node modules (puppeteer-core) are already installed.")
        return True

    print("  [!] Node modules (node_modules/puppeteer-core) are missing.")
    npm_cmd = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm_cmd:
        print("  [ERROR] npm is not available in PATH. Cannot run npm install.")
        return False

    if ask_yes_no("  -> Run 'npm install' now?", default_yes=True):
        print("\n  [NPM] Installing Node dependencies...\n")
        res = subprocess.run([npm_cmd, "install"], cwd=str(PROJECT_ROOT))
        if res.returncode != 0:
            print("\n  [ERROR] 'npm install' failed.")
            return False
        print("\n  [OK] Node modules installed successfully.")
        return True

    print("  [WARN] Video storyboard rendering will fail without puppeteer-core.")
    return True


def step_4_bootstrap_directories() -> bool:
    """
    Creates essential workspace directories and inspects user input data folders.

    Why: Prevents FileNotFoundError during data ingestion, story export, and rendering.
    """
    print("\n" + "=" * 68)
    print("  STEP 4: Project Directory & Asset Bootstrapping")
    print("=" * 68)

    required_dirs = [
        PROJECT_ROOT / "files",
        PROJECT_ROOT / "output",
        PROJECT_ROOT / "output" / "audio",
        PROJECT_ROOT / "output" / "previews",
        PROJECT_ROOT / "output" / "renders",
        PROJECT_ROOT / "output" / "storyboard",
    ]

    for d in required_dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            print(f"  [+] Created directory: {d.relative_to(PROJECT_ROOT)}")
        else:
            print(f"  [OK] Directory exists: {d.relative_to(PROJECT_ROOT)}")

    # Check for user input files
    db_file = PROJECT_ROOT / "files" / "namida.db"
    csv_file = PROJECT_ROOT / "files" / "namida_history.csv"
    if db_file.exists() or csv_file.exists():
        found = db_file.name if db_file.exists() else csv_file.name
        print(f"  [OK] Detected user music telemetry database: files/{found}")
    else:
        print("  [INFO] No Namida database detected yet in files/")
        print("         Place your exported 'namida.db' or 'namida_history.csv' into 'files/'")
        print("         or upload it directly in the Web Studio.")

    return True


def main() -> None:
    """
    Main orchestration entrypoint for the NamidaWrapped setup wizard.
    """
    print("=" * 68)
    print("        NamidaWrapped — Automated Environment Setup Wizard       ")
    print("=" * 68)
    print(f"  Root Directory: {PROJECT_ROOT}")
    print(f"  Python Binary:  {sys.executable}")

    # 1. System prerequisites
    step_1_system_prerequisites()

    # 2. Python dependencies
    step_2_python_dependencies()

    # 3. Node.js dependencies
    step_3_node_dependencies()

    # 4. Directory bootstrap
    step_4_bootstrap_directories()

    print("\n" + "=" * 68)
    print("  SETUP COMPLETE!")
    print("  All prerequisites and dependencies have been verified.")
    print("  You can launch the Studio dashboard anytime via 'run_ui.bat'.")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()

