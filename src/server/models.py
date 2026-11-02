"""
Pydantic V2 Schemas for 2026 Wrapped Web Studio.
Author: Antigravity
Python: 3.13.12
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class SpotifyAdditionsModel(BaseModel):
    """Spotify cross-platform supplemental metrics."""
    extra_minutes: int = Field(default=0, ge=0, description="Additional minutes listened from Spotify")
    extra_plays: int = Field(default=0, ge=0, description="Additional plays from Spotify")
    extra_songs: int = Field(default=0, ge=0, description="Additional unique songs from Spotify")
    streak_days: int = Field(default=103, ge=1, description="Longest listening streak in days")


class ListeningClockModel(BaseModel):
    """Listening clock workday and weekend adjustments."""
    workday_hours_start: int = Field(default=7, ge=0, le=23)
    workday_hours_end: int = Field(default=15, ge=0, le=23)
    workday_extra_minutes: int = Field(default=15000, ge=0)
    saturday_extra_minutes: int = Field(default=1450, ge=0)


class CuratedSongModel(BaseModel):
    """Single curated track item."""
    rank: int = Field(ge=1, le=5)
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    artwork: str = Field(default="")
    path: Optional[str] = None


class CuratedAlbumModel(BaseModel):
    """Single curated album item."""
    rank: int = Field(ge=1, le=5)
    album: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    artwork: str = Field(default="")
    path: Optional[str] = None


class CuratedArtistModel(BaseModel):
    """Single curated artist item."""
    rank: int = Field(ge=1, le=5)
    name: str = Field(min_length=1)
    image: str = Field(default="")


class CuratedDiscoveryModel(BaseModel):
    """Single curated discovery item."""
    rank: int = Field(ge=1, le=5)
    name: str = Field(min_length=1)
    image: str = Field(default="")


class CuratedGenreModel(BaseModel):
    """Single curated genre item with representative song, artist, and optional local audio path."""
    rank: int = Field(ge=1, le=5)
    genre: str = Field(min_length=1)
    song: str = Field(min_length=1)
    artist: Optional[str] = Field(default="", description="Artist name")
    path: Optional[str] = Field(default=None, description="Local audio file path")
    artwork: Optional[str] = Field(default="", description="Cover art data URI")


class PanelSubmissionRequest(BaseModel):
    """Submission payload for a specific panel step."""
    panel_id: int = Field(ge=0, le=9)
    data: dict[str, Any] = Field(description="Dynamic panel payload corresponding to panel_id")


class FLACExtractRequest(BaseModel):
    """Request to extract metadata and artwork from a local audio file (or default soundtrack if empty)."""
    path: str = Field(default="", description="Local filesystem path to audio file")


class FLACExtractResponse(BaseModel):
    """Extracted metadata, duration, and Base64 artwork response."""
    path: str
    title: str
    artist: str
    album: str
    artwork: str
    duration: float = 0.0
    valid: bool


class BrowseAudioRequest(BaseModel):
    """Request payload for opening the native Windows File Explorer to select an audio file."""
    initial_path: Optional[str] = Field(default=None, description="Optional existing file or folder path")


class PreviewFpsRequest(BaseModel):
    """Request payload to update the global preview framerate."""
    fps: int = Field(ge=1, le=60, description="Global preview framerate (1 to 60 FPS)")


class RenderSliceRequest(BaseModel):
    """Optional request payload to specify framerate when rendering a preview slice."""
    fps: Optional[int] = Field(default=None, ge=1, le=60, description="Preview framerate in frames per second")


class SaveVideoRequest(BaseModel):
    """Request payload to export rendered video to a custom destination file path."""
    target_path: str = Field(min_length=1, description="Destination path for .mp4 file")
    panel_id: Optional[int] = Field(default=None, description="Optional panel slice index or full video if None")
    selected_panels: Optional[list[int]] = Field(default=None, description="Optional custom sequence of panel indices")
    render_first: bool = Field(default=True, description="Whether to re-render fresh video according to parameters before saving")
    fps: Optional[int] = Field(default=None, ge=1, le=60, description="Optional framerate override")


class ExportSliceRequest(BaseModel):
    """Request to export a single isolated panel slice."""
    panel_id: int = Field(ge=0, le=9, description="Panel index (0 to 9)")
    target_path: Optional[str] = Field(default=None, description="Optional destination path")
    fps: Optional[int] = Field(default=None, ge=1, le=60, description="Optional framerate override")


class RenderCustomVideoRequest(BaseModel):
    """Request to render a customized composite video from selected slices and order."""
    selected_panels: list[int] = Field(min_length=1, description="Ordered list of panel indices to include")
    target_path: Optional[str] = Field(default=None, description="Optional destination path")
    fps: Optional[int] = Field(default=None, ge=1, le=60, description="Optional preview or export framerate")


class ThemeModel(BaseModel):
    """Dynamic ambient background color palette and highlights model."""
    id: str = Field(default="aurora", description="Palette ID (aurora, cyberpunk, sunset, midnight, acid, custom)")
    primary: str = Field(default="#00ff87", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", description="Primary glow hex color")
    secondary: str = Field(default="#7928ca", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", description="Secondary glow hex color")
    accent: str = Field(default="#ff007a", pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", description="Accent glow hex color")
    tertiary: Optional[str] = Field(default="#00d4ff", description="Tertiary fill hex color")
    bg_base: Optional[str] = Field(default="#030604", description="Deep background base hex color")
    bg_mid: Optional[str] = Field(default="#0c2616", description="Ambient gradient center hex color")
    bg_outer: Optional[str] = Field(default="#07140b", description="Ambient gradient outer hex color")


class PanelStatusResponse(BaseModel):
    """Studio overall state and preview urls."""
    current_panel: int
    completed_panels: list[int]
    total_panels: int = 10
    duration_up_to_current: float
    curation_data: dict[str, Any]
    telemetry_baselines: Optional[dict[str, Any]] = None
    preview_url: str
    video_slice_url: Optional[str] = None
    single_slice_url: Optional[str] = None
    preview_fps: int = 1
    is_rendering: bool = False
    render_progress: float = 0.0


