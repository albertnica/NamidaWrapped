# Namida Wrapped: Workspace Directives & Operational Rules

## 1. Language & Documentation Standards
- **English Strict**: All source code, docstrings, comments, commits, and documentation must be written strictly in English.
- **Documentation Quality**: Comments must explain the architectural "Why", never the obvious "What". Every exported function and class must include strict type annotations and docstrings (Google/Sphinx style for Python, JSDoc/TSDoc for JavaScript/TypeScript).

## 2. Verification & Browser Workflow
- **Recompile Pipeline**: Always recompile the storyboard via `python main.py generate` and verify preview keyframes via `node src/renderer/preview_engine.js` whenever templates (`src/templates/`) or data sources are altered.
- **Browser Automation**: Use headless Chrome / Puppeteer inspection proactively to audit element bounding boxes, detect collisions, and verify visual integrity before user handover.
- **Live Studio Relaunch**: Relaunch or focus the browser process (`Start-Process 'http://127.0.0.1:8000'`) whenever UI templates, server endpoints, or styles are updated.

## 3. Layout & Typography Constraints (1080x1920 Storyboard)
- **Viewport Encapsulation**: All slide layouts must be nested strictly inside `.content-viewport` (`top: 165px; bottom: 110px; left: 55px; right: 55px;`) to prevent vertical collisions with the header navigation bar (`top: 62px;`) and bottom playback deck (`bottom: 35px;`).
- **Typography Floor**: Due to $0.333\times$–$0.444\times$ iframe downscaling in the Web Studio desktop mockup, no visible text element may fall below **34px**. Primary hero titles must scale to **120px–124px**, and key numeric metrics must scale to **110px–148px**.
- **Flexbox & Overflow Integrity**: Dynamic metric cards (e.g., `.rhythm-val`) must enforce `white-space: nowrap` and explicit container height boundaries to prevent layout reflow collisions.

## 4. Stack & Runtime Environment
- **Backend**: Python 3.13+ using FastAPI, Pydantic V2 schemas, and asynchronous endpoints. Must run inside the local virtual environment (`.venv`).
- **Renderer**: Node.js with Puppeteer and native FFmpeg integration for high-throughput headless canvas captures and MP4 compilation.
- **Dependency Automation**: All setup prerequisites and package installations must be handled cleanly via `setup.bat` and `setup_wizard.py`.
