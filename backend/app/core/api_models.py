"""API-layer request/response models — kept separate from core schemas so
the internal stage contracts can evolve independently of the public API."""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel

from app.core.schemas import ClaimObjectType, FinalVerdict


class CreateClaimRequest(BaseModel):
    user_id: str
    claim_object: ClaimObjectType
    user_claim: str
    user_provided_model: Optional[str] = None
    user_provided_serial: Optional[str] = None
    user_provided_plate: Optional[str] = None
    user_provided_vin: Optional[str] = None
    policy_start_date: Optional[str] = None
    registered_region: Optional[str] = None
    past_claim_count: int = 0
    rejected_claim_count: int = 0


class CreateClaimResponse(BaseModel):
    claim_id: str
    challenge_code: str
    message: str


class ClaimSummary(BaseModel):
    claim_id: str
    user_id: str
    claim_object: str
    status: str
    created_at: str
    overall_claim_trust_score: Optional[float] = None
    claim_status: Optional[str] = None
    requires_manual_review: Optional[bool] = None


class ClaimListResponse(BaseModel):
    claims: List[ClaimSummary]


class ClaimDetailResponse(BaseModel):
    claim_id: str
    status: str
    verdict: Optional[FinalVerdict] = None
    image_paths: Optional[List[str]] = None
    video_path: Optional[str] = None
    challenge_code: Optional[str] = None
    user_claim: Optional[str] = None
    claim_object: Optional[str] = None


class NetworkClaimRef(BaseModel):
    claim_id: str
    user_id: str
    claim_object: str
    image_paths: List[str]
    created_at: str
