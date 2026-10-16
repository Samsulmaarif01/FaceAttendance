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


class RecognizeResponse(BaseModel):
    faces: List[FaceResult]
    count: int
    elapsed_ms: float


class EnrollResponse(BaseModel):
    success: bool
    user_id: str
    name: str
    embedding_dim: int


class UserInfo(BaseModel):
    id: str
    name: str
    is_active: bool
    created_at: str
    attendance_count: int = 0
    last_attendance: Optional[str] = None


class UsersResponse(BaseModel):
    users: List[UserInfo]
    count: int


class DeleteResponse(BaseModel):
    success: bool
    id: Optional[str] = None
    deleted: Optional[int] = None


class AttendanceInfo(BaseModel):
    id: str
    user_id: str
    timestamp: str
    similarity: float
    liveness_score: float
    synced: bool


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
