"""
FastAPI Application for 2026 Wrapped Web Studio.
Author: Antigravity
Python: 3.13.12
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys
from typing import Any
from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Silence harmless Windows Proactor 10054 ConnectionResetError during HTML5 video range scrubbing
if sys.platform == "win32":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _safe_call_connection_lost(self: Any, exc: Any) -> None:
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                pass

        _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Global lifespan context managing loop exception handlers for graceful socket drops."""
    loop = asyncio.get_running_loop()
    default_handler = loop.get_exception_handler()

    def proactor_exception_handler(current_loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        exc = context.get("exception")
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)):
            return
        if getattr(exc, "winerror", None) == 10054:
            return
        if default_handler:
            default_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(proactor_exception_handler)
    yield


from src.config import (
    CURRENT_YEAR,
    CUSTOM_VIDEO_PATH,
    OUTPUT_DIR,
    OUTPUT_VIDEO_PATH,
    ROOT_DIR,
    SLICES_DIR,
    STORY_HTML_PATH,
)
from src.server.models import (
    BrowseAudioRequest,
    ExportSliceRequest,
    FLACExtractRequest,
    FLACExtractResponse,
    PanelStatusResponse,
    PanelSubmissionRequest,
    PreviewFpsRequest,
    RenderCustomVideoRequest,
    RenderSliceRequest,
    SaveVideoRequest,
    ThemeModel,
)
from src.server.service import studio_service

app = FastAPI(
    title="2026 Wrapped Web Studio",
    description="Interactive Split-Screen Curation Terminal and Real-Time Story Preview Engine",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Mount outputs (rendered MP4, soundtracks, images)
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico")
async def favicon() -> Response:
    """Returns empty 204 to suppress 404 terminal logs."""
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    """Serves the main split-screen Web Studio application."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Studio frontend not found.")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.get("/story", response_class=HTMLResponse)
async def serve_story_iframe() -> HTMLResponse:
    """Serves the compiled offline story.html for zero-latency iframe preview."""
    if not STORY_HTML_PATH.exists():
        studio_service.builder.build(output_file=STORY_HTML_PATH)
    return HTMLResponse(content=STORY_HTML_PATH.read_text(encoding="utf-8"))


def _output_url(file_path: Path) -> str:
    """Converts a file path inside OUTPUT_DIR into a /output/... URL."""
    try:
        rel = file_path.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()
        return f"/output/{rel}"
    except Exception:
        return f"/output/{file_path.name}"


@app.get("/api/status", response_model=PanelStatusResponse)
async def get_status() -> PanelStatusResponse:
    """Returns the current wizard progress, completed panels, and preview targets."""
    cur_p = studio_service.current_panel
    duration = round((cur_p + 1) * 5.0, 2)
    slice_path = SLICES_DIR / f"wrapped_slice_panel_{cur_p}.mp4"
    single_path = SLICES_DIR / f"wrapped_slice_single_{cur_p}.mp4"
    custom_path = CUSTOM_VIDEO_PATH
    full_video_path = OUTPUT_VIDEO_PATH

    single_url = _output_url(single_path) if single_path.exists() else None

    # Prioritize active panel slice if available, then fallback to last rendered video
    if single_path.exists():
        video_url = _output_url(single_path)
    elif studio_service.last_slice_file and studio_service.last_slice_file.exists():
        video_url = _output_url(studio_service.last_slice_file)
    elif slice_path.exists():
        video_url = _output_url(slice_path)
    elif custom_path.exists():
        video_url = _output_url(custom_path)
    elif full_video_path.exists():
        video_url = _output_url(full_video_path)
    else:
        video_url = None

    return PanelStatusResponse(
        current_panel=cur_p,
        completed_panels=sorted(list(studio_service.completed_panels)),
        total_panels=10,
        duration_up_to_current=duration,
        curation_data=studio_service.get_curation(),
        telemetry_baselines=studio_service.get_telemetry_baselines(),
        preview_url=f"/story?t={duration}",
        video_slice_url=video_url,
        single_slice_url=single_url,
        preview_fps=studio_service.get_preview_fps(),
        is_rendering=studio_service.is_rendering,
        render_progress=studio_service.render_progress
    )


@app.post("/api/preview-fps")
async def update_preview_fps(req: PreviewFpsRequest) -> dict[str, Any]:
    """Updates and persists the global preview framerate (1 to 60 FPS)."""
    saved_fps = studio_service.set_preview_fps(req.fps)
    return {"status": "ok", "preview_fps": saved_fps}


@app.get("/api/theme", response_model=ThemeModel)
async def get_current_theme() -> dict[str, Any]:
    """Returns the currently active theme palette and background glow colors."""
    return studio_service.get_theme()


@app.post("/api/theme", response_model=ThemeModel)
async def update_current_theme(theme: ThemeModel) -> dict[str, Any]:
    """Updates and persists the background theme palette, immediately rebuilding story.html."""
    return studio_service.set_theme(theme.model_dump())


@app.post("/api/browse-path")
async def browse_save_path() -> dict[str, Any]:
    """Triggers native OS Save As dialog to choose file destination."""
    path = await asyncio.to_thread(studio_service.browse_save_path)
    return {"selected_path": path}


@app.post("/api/browse-audio")
async def browse_audio_file(req: BrowseAudioRequest | None = None) -> dict[str, Any]:
    """Triggers native Windows File Explorer Open File dialog to choose a local audio file."""
    initial_path = req.initial_path if req else None
    path = await asyncio.to_thread(studio_service.browse_audio_file, initial_path)
    return {"selected_path": path}


@app.post("/api/save-video")
async def save_rendered_video(req: SaveVideoRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Exports or renders video directly to a user-specified destination path on disk."""
    if req.render_first:
        if studio_service.is_rendering:
            return {"status": "busy", "message": "Rendering is already in progress."}

        if req.selected_panels is not None and len(req.selected_panels) > 0:
            background_tasks.add_task(studio_service.render_custom_sequence, req.selected_panels, req.target_path, req.fps or 25)
            mode_desc = f"custom sequence of {len(req.selected_panels)} slice(s)"
            target_file = "renders/wrapped_custom_export.mp4"
        elif req.panel_id is not None:
            background_tasks.add_task(studio_service.render_isolated_slice, req.panel_id, req.target_path, req.fps or 25)
            mode_desc = f"slice for panel {req.panel_id + 1}"
            target_file = f"slices/wrapped_slice_single_{req.panel_id}.mp4"
        else:
            background_tasks.add_task(studio_service.render_full_video, req.target_path, req.fps or 25)
            mode_desc = f"full presentation ({CURRENT_YEAR})"
            target_file = f"renders/wrapped_{CURRENT_YEAR}.mp4"

        return {
            "status": "started",
            "message": f"Rendering {mode_desc} with current parameters and saving to {req.target_path}...",
            "target_file": target_file
        }
    else:
        try:
            return studio_service.save_video_to_disk(req.target_path, req.panel_id, req.selected_panels)
        except FileNotFoundError as err:
            raise HTTPException(status_code=404, detail=str(err))
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Failed to save video: {err}")


@app.post("/api/panels/{panel_id}/save")
async def save_panel_data_local(panel_id: int, req: PanelSubmissionRequest) -> dict[str, Any]:
    """Persists inputs for panel_id into non-committed local JSON files and recompiles story.html."""
    if panel_id < 0 or panel_id > 9:
        raise HTTPException(status_code=400, detail="Invalid panel_id (must be 0-9).")
    return studio_service.save_panel_local(panel_id, req.data)


@app.post("/api/panels/{panel_id}", response_model=PanelStatusResponse)
async def submit_panel_data(panel_id: int, req: PanelSubmissionRequest) -> PanelStatusResponse:
    """Receives and validates input for panel_id, updating story.html immediately."""
    if panel_id < 0 or panel_id > 9:
        raise HTTPException(status_code=400, detail="Invalid panel_id (must be 0-9).")

    studio_service.update_panel(panel_id, req.data)
    return await get_status()


@app.post("/api/panels/{panel_id}/confirm", response_model=PanelStatusResponse)
async def confirm_panel(panel_id: int) -> PanelStatusResponse:
    """Confirms current panel and advances to the next one."""
    studio_service.confirm_and_advance(panel_id)
    return await get_status()


@app.post("/api/panels/{panel_id}/goto", response_model=PanelStatusResponse)
async def goto_panel(panel_id: int) -> PanelStatusResponse:
    """Switches the active step to panel_id."""
    studio_service.set_current_panel(panel_id)
    return await get_status()


@app.post("/api/panels/{panel_id}/render-slice")
async def trigger_slice_render(
    panel_id: int,
    background_tasks: BackgroundTasks,
    req: RenderSliceRequest | None = None,
) -> dict[str, Any]:
    """Schedules background rendering of an MP4 video slice preview up to panel_id at configured preview FPS."""
    if studio_service.is_rendering:
        return {"status": "busy", "message": "Rendering is already in progress."}

    fps = studio_service.set_preview_fps(req.fps) if (req and req.fps) else studio_service.get_preview_fps()
    background_tasks.add_task(studio_service.render_video_slice, panel_id, fps)
    return {
        "status": "started",
        "panel_id": panel_id,
        "fps": fps,
        "duration_sec": round((panel_id + 1) * 5.0, 2),
        "target_file": f"slices/wrapped_slice_panel_{panel_id}.mp4"
    }


@app.post("/api/panels/{panel_id}/render-isolated")
async def trigger_isolated_slice_render(
    panel_id: int,
    background_tasks: BackgroundTasks,
    req: RenderSliceRequest | None = None,
) -> dict[str, Any]:
    """Schedules background rendering of ONLY this panel's 5.0s slice preview at configured preview FPS."""
    if studio_service.is_rendering:
        return {"status": "busy", "message": "Rendering is already in progress."}

    fps = studio_service.set_preview_fps(req.fps) if (req and req.fps) else studio_service.get_preview_fps()
    background_tasks.add_task(studio_service.render_isolated_slice, panel_id, None, fps)
    return {
        "status": "started",
        "panel_id": panel_id,
        "fps": fps,
        "duration_sec": 5.0,
        "target_file": f"slices/wrapped_slice_single_{panel_id}.mp4"
    }


@app.post("/api/render-custom")
async def trigger_custom_render(req: RenderCustomVideoRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Renders a custom composite video from chosen slices and order (configured preview FPS for preview, 25 FPS for export)."""
    if studio_service.is_rendering:
        return {"status": "busy", "message": "Rendering is already in progress."}

    if req.fps:
        fps = studio_service.set_preview_fps(req.fps) if not req.target_path else max(1, min(60, req.fps))
    else:
        fps = 25 if req.target_path else studio_service.get_preview_fps()
    background_tasks.add_task(studio_service.render_custom_sequence, req.selected_panels, req.target_path, fps)
    return {
        "status": "started",
        "selected_panels": req.selected_panels,
        "fps": fps,
        "duration_sec": round(len(req.selected_panels) * 5.0, 2),
        "target_file": "renders/wrapped_custom_export.mp4"
    }


@app.post("/api/render-full")
async def trigger_full_render(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Schedules background rendering of the full 10-slide 50.0s presentation at complete 25 FPS."""
    if studio_service.is_rendering:
        return {"status": "busy", "message": "Rendering is already in progress."}

    background_tasks.add_task(studio_service.render_full_video, None, 25)
    return {
        "status": "started",
        "duration_sec": 50.0,
        "fps": 25,
        "target_file": f"renders/wrapped_{CURRENT_YEAR}.mp4"
    }


@app.post("/api/extract-flac", response_model=FLACExtractResponse)
async def extract_flac_metadata(req: FLACExtractRequest) -> FLACExtractResponse:
    """Parses local audio file tags (FLAC, MP3, M4A), duration, and extracts cover art."""
    meta = studio_service.extract_flac(req.path)
    return FLACExtractResponse(
        path=meta["path"],
        title=meta["title"],
        artist=meta["artist"],
        album=meta["album"],
        artwork=meta.get("artwork", ""),
        duration=meta.get("duration", 0.0),
        valid=meta["valid"]
    )


@app.get("/api/audio-stream")
async def stream_audio_file(path: str = "") -> Response:
    """Streams the full audio file with HTTP Range support for real-time mini-player & preview seeking."""
    stream_p, mime_type = studio_service.resolve_audio_stream_path(path)
    if not stream_p or not stream_p.exists():
        raise HTTPException(status_code=404, detail="Audio track not found.")
    return FileResponse(stream_p, media_type=mime_type)


@app.get("/api/audio-preview-clip")
async def get_audio_preview_clip(path: str = "", start: float = 0.0) -> Response:
    """Streams a 5.0-second AAC audio snippet with 1s fade-in and 1s fade-out for browser playback."""
    clip_p = studio_service.generate_audio_snippet(path, start)
    if not clip_p or not clip_p.exists():
        raise HTTPException(status_code=404, detail="Could not generate audio preview clip.")
    return FileResponse(clip_p, media_type="audio/aac")


@app.post("/api/shutdown")
async def shutdown_studio_server() -> dict[str, Any]:
    """Terminates the background Web Studio server process cleanly from the UI."""
    import os
    import threading

    def _delayed_exit() -> None:
        os._exit(0)

    threading.Timer(0.35, _delayed_exit).start()
    return {"status": "shutting_down", "message": "Studio server stopped."}


