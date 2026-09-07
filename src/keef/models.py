from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ConnectionState(StrEnum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class SlskdStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    soulseek_connected: bool | None = None
    username: str | None = None
    state: ConnectionState = ConnectionState.UNKNOWN


class SlskdServerState(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    is_connected: bool | None = Field(default=None, alias="isConnected")
    is_logged_in: bool | None = Field(default=None, alias="isLoggedIn")
    username: str | None = None


class ConnectionReport(BaseModel):
    reachable: bool
    authenticated: bool | None = None
    soulseek_connected: bool | None = None
    account: str | None = None
    detail: str | None = None


class MusicTrack(BaseModel):
    path: str
    format: str = "unknown"
    codec: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    duration_seconds: float | None = None
    bitrate_kbps: int | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    lossless: bool | None = None
    missing_metadata: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    search_text: str = Field(min_length=1)
    search_timeout: int = Field(default=5, ge=1)
    response_limit: int = Field(default=100, ge=1)


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: UUID
    responses: list[dict[str, Any]] = Field(default_factory=list)


class SearchCandidate(BaseModel):
    username: str
    filename: str
    size: int = Field(ge=0)
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    duration_seconds: float | None = None
    bitrate_kbps: int | None = Field(default=None, ge=0)
    format: str | None = None
    lossless: bool | None = None


class MatchResult(BaseModel):
    candidate: SearchCandidate
    score: float = Field(ge=0, le=1)
    accepted: bool
    ambiguous: bool
    reasons: list[str] = Field(default_factory=list)


class QualityPolicy(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"
    EXACT = "exact"


class QualityDecision(BaseModel):
    eligible: bool
    reason: str


class AlbumScan(BaseModel):
    folder_name: str
    artist: str | None = None
    album: str | None = None
    tracks: list[MusicTrack] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    track_count: int = 0


class AlbumFileMatch(BaseModel):
    local_track: MusicTrack
    remote_filename: str
    remote_size: int
    score: float = Field(ge=0, le=1)
    quality: QualityDecision


class AlbumMatch(BaseModel):
    username: str
    file_count: int
    matched_files: list[AlbumFileMatch] = Field(default_factory=list)
    unmatched_locals: list[str] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0, le=1)
    accepted: bool = False


class AlbumMatchResult(BaseModel):
    album: AlbumScan
    matches: list[AlbumMatch] = Field(default_factory=list)
    error: str | None = None


class MetadataReport(BaseModel):
    tracks: list[MusicTrack] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class BatchPreviewItem(BaseModel):
    track: MusicTrack
    candidates: list[MatchResult] = Field(default_factory=list)
    quality_decisions: list[QualityDecision] = Field(default_factory=list)
    error: str | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
