"""Pydantic schemas for the local web API (phase 6)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    demo_mode: bool
    recognition_models: int
    detector_loaded: bool
    matcher_backend: str
    sync_enabled: bool
    # Diagnostic: if templates_unreadable > 0 the encryption key no longer
    # matches the stored templates and NOTHING can ever be recognised.
    templates_loaded: int = 0
    templates_unreadable: int = 0
    templates_unreadable_ids: List[str] = Field(default_factory=list)
    enroll_duplicate_threshold: Optional[float] = None


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class LivenessInfo(BaseModel):
    is_live: bool
    score: float
    reason: str


class MatchInfo(BaseModel):
    user_id: str
    name: str
    similarity: float
    threshold: float
    matched: bool


class FaceResult(BaseModel):
    bbox: BBox
    confidence: float
    liveness: LivenessInfo
    match: Optional[MatchInfo] = None
    attendance_logged: bool = False
    attendance_duplicate: bool = False
    attendance_duplicate_at: Optional[str] = None
    attendance_status: str = "no_match"
    gate_granted: bool = False
    direction: str = "in"


class RecognizeResponse(BaseModel):
    faces: List[FaceResult]
    count: int
    elapsed_ms: float


class EnrollResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None
    name: str = ""
    embedding_dim: int = 0
    confidence: Optional[float] = None
    # Duplicate guard: set when the face already belongs to a known user.
    duplicate: bool = False
    existing_user_id: Optional[str] = None
    existing_name: Optional[str] = None
    existing_is_active: Optional[bool] = None
    similarity: Optional[float] = None
    updated: bool = False        # template refreshed for the same user_id
    reactivated: bool = False    # soft-deleted owner restored, history kept
    has_photo: bool = False      # avatar thumbnail stored


class UserInfo(BaseModel):
    id: str
    name: str
    is_active: bool
    is_archived: bool = False
    created_at: str
    attendance_count: int = 0
    last_attendance: Optional[str] = None
    checked_in_today: bool = False
    checked_out_today: bool = False
    has_photo: bool = False


class UsersResponse(BaseModel):
    users: List[UserInfo]
    count: int


class DeleteResponse(BaseModel):
    success: bool
    id: Optional[str] = None
    deleted: Optional[int] = None
    # "archived" | "permanent" | "restored"
    mode: Optional[str] = None
    attendance_deleted: int = 0


class PhotoResponse(BaseModel):
    """Result of attaching a fresh avatar to an existing user (photo-only)."""

    success: bool
    user_id: str
    has_photo: bool = True
    bytes: int = 0


class AttendanceInfo(BaseModel):
    id: str
    user_id: str
    timestamp: str
    similarity: float
    liveness_score: float
    synced: bool
    direction: str = "in"
    name: Optional[str] = None   # kept even when the user was soft-deleted


class AttendanceResponse(BaseModel):
    records: List[AttendanceInfo]
    count: int


class StatsResponse(BaseModel):
    total: int
    users: int
    synced: int
    pending: int


class SyncResponse(BaseModel):
    status: str
    success: Optional[bool] = None
    uploaded: Optional[int] = None
    synced_ids: List[str] = Field(default_factory=list)
    retry_delay: Optional[float] = None
    error: Optional[str] = None
