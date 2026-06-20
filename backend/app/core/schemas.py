"""
Core data schemas for the InsureVerify platform.
Every stage produces a structured, typed output that feeds into the next stage
and ultimately into the Judge Agent's final verdict. This is what makes the
system auditable: every number and label in the final verdict traces back to
a specific stage's output.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


# ---------------------------------------------------------------------------
# Enums — closed taxonomies. The platform NEVER emits free-text labels for
# these fields, only values from these enums. This keeps downstream
# analytics, dashboards and audits consistent.
# ---------------------------------------------------------------------------

class ClaimObjectType(str, Enum):
    car = "car"
    laptop = "laptop"
    package = "package"


class ClaimStatus(str, Enum):
    supported = "supported"
    contradicted = "contradicted"
    not_enough_information = "not_enough_information"


class Severity(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    unknown = "unknown"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"


class RiskFlag(str, Enum):
    ai_generated_image = "ai_generated_image"
    photoshopped_damage = "photoshopped_damage"
    reused_claim_photo = "reused_claim_photo"
    internet_downloaded_image = "internet_downloaded_image"
    wrong_object = "wrong_object"
    old_evidence = "old_evidence"
    inconsistent_serial_number = "inconsistent_serial_number"
    claim_mismatch = "claim_mismatch"
    manipulated_metadata = "manipulated_metadata"
    mixed_evidence_multiple_devices = "mixed_evidence_multiple_devices"
    insufficient_evidence = "insufficient_evidence"
    possession_not_verified = "possession_not_verified"
    ownership_not_verified = "ownership_not_verified"
    timestamp_before_policy_start = "timestamp_before_policy_start"
    geo_location_mismatch = "geo_location_mismatch"
    duplicate_claim_network = "duplicate_claim_network"
    liveness_check_failed = "liveness_check_failed"
    high_risk_claimant_history = "high_risk_claimant_history"


# ---------------------------------------------------------------------------
# Stage 0 — Evidence Authenticity
# ---------------------------------------------------------------------------

class MetadataReport(BaseModel):
    camera_model: Optional[str] = None
    timestamp: Optional[str] = None
    editing_software: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    has_exif: bool = False
    suspicious_metadata: bool = False
    metadata_flags: List[str] = Field(default_factory=list)


class ELAReport(BaseModel):
    ela_mean: float
    ela_max: float
    suspicious_regions: List[List[int]] = Field(default_factory=list)  # bounding boxes [x,y,w,h]
    manipulation_score: float  # 0-1


class AIGeneratedReport(BaseModel):
    ai_generation_probability: float  # 0-1
    manipulation_confidence: float  # 0-1
    signals: List[str] = Field(default_factory=list)


class ReflectionConsistencyReport(BaseModel):
    lighting_consistency_score: float  # 0-1, higher = more consistent
    shadow_consistency_score: float
    notes: List[str] = Field(default_factory=list)


class CrossImageConsistencyReport(BaseModel):
    same_object_across_images: bool
    mixed_evidence_detected: bool
    duplicate_phash_matches: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class PerImageAuthenticity(BaseModel):
    image_path: str
    metadata: MetadataReport
    ela: ELAReport
    ai_generated: AIGeneratedReport
    reflection: ReflectionConsistencyReport
    phash: str
    image_authenticity_score: float  # 0-1, higher = more trustworthy


class AuthenticityEngineOutput(BaseModel):
    per_image: List[PerImageAuthenticity]
    cross_image: CrossImageConsistencyReport
    authenticity_score: float  # 0-1 aggregate
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 1 — Ownership Verification
# ---------------------------------------------------------------------------

class OwnershipEvidence(BaseModel):
    detected_text: List[str] = Field(default_factory=list)
    detected_brand: Optional[str] = None
    detected_model: Optional[str] = None
    detected_serial: Optional[str] = None
    detected_vin: Optional[str] = None
    detected_plate: Optional[str] = None


class OwnershipEngineOutput(BaseModel):
    evidence: OwnershipEvidence
    matches_user_provided_details: bool
    ownership_score: float  # 0-1
    flags: List[RiskFlag] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 2 — Possession Verification (challenge code)
# ---------------------------------------------------------------------------

class PossessionEngineOutput(BaseModel):
    challenge_code: str
    challenge_code_detected: bool
    detected_codes: List[str] = Field(default_factory=list)
    possession_score: float  # 0-1
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 3 — Damage Liveness (video)
# ---------------------------------------------------------------------------

class LivenessEngineOutput(BaseModel):
    video_provided: bool
    frame_count_analyzed: int = 0
    damage_consistent_across_frames: bool = False
    motion_naturalness_score: float = 0.0  # 0-1, heuristic for "real handheld video" vs static/looped
    damage_liveness_score: float = 0.0  # 0-1
    flags: List[RiskFlag] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 4 — Evidence Sufficiency
# ---------------------------------------------------------------------------

class SufficiencyEngineOutput(BaseModel):
    required_views: List[str]
    detected_views: List[str]
    missing_views: List[str]
    coverage_score: float  # 0-1
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 5 — Vision Language Analysis (VLM, blind to claim text)
# ---------------------------------------------------------------------------

class VisionObservation(BaseModel):
    image_path: str
    objective_description: str
    detected_object: Optional[str] = None
    detected_part: Optional[str] = None
    detected_issue: Optional[str] = None
    severity: Severity = Severity.unknown
    confidence: float = 0.0


class VisionAnalysisOutput(BaseModel):
    observations: List[VisionObservation]
    aggregate_part: Optional[str] = None
    aggregate_issue: Optional[str] = None
    aggregate_severity: Severity = Severity.unknown


# ---------------------------------------------------------------------------
# Stage 6 — Claim Understanding (NLP on user's free text)
# ---------------------------------------------------------------------------

class ClaimUnderstandingOutput(BaseModel):
    claimed_object: Optional[str] = None
    claimed_part: Optional[str] = None
    claimed_issue: Optional[str] = None
    claimed_cause: Optional[str] = None
    raw_text: str


# ---------------------------------------------------------------------------
# Stage 7 — Story Consistency
# ---------------------------------------------------------------------------

class StoryConsistencyOutput(BaseModel):
    expected_damage_pattern: str
    observed_damage_pattern: str
    is_consistent: bool
    consistency_score: float  # 0-1
    reasoning: str
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 8 — Physics-Based Damage Validation
# ---------------------------------------------------------------------------

class PhysicsValidationOutput(BaseModel):
    fracture_pattern: Optional[str] = None  # "branching", "radial", "random_lines", "none"
    impact_point_detected: bool = False
    physically_plausible: bool = True
    damage_authenticity_score: float = 0.5  # 0-1
    notes: List[str] = Field(default_factory=list)
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 9 — User Risk Engine
# ---------------------------------------------------------------------------

class UserRiskOutput(BaseModel):
    past_claim_count: int
    rejected_claim_count: int
    rejection_rate: float
    history_flags: List[str] = Field(default_factory=list)
    claimant_risk_score: float  # 0-1, higher = riskier
    risk_level: RiskLevel
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 10 — Adaptive Verification (what extra evidence to demand)
# ---------------------------------------------------------------------------

class AdaptiveVerificationOutput(BaseModel):
    risk_level: RiskLevel
    required_steps: List[str]
    satisfied_steps: List[str]
    pending_steps: List[str]


# ---------------------------------------------------------------------------
# Stage X (bonus / unique) — Fraud Ring / Duplicate Network Detection
# ---------------------------------------------------------------------------

class FraudNetworkOutput(BaseModel):
    duplicate_image_claim_ids: List[str] = Field(default_factory=list)
    shared_serial_claim_ids: List[str] = Field(default_factory=list)
    shared_device_other_users: List[str] = Field(default_factory=list)
    network_risk_score: float = 0.0  # 0-1
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage X (bonus) — Temporal & Geo Consistency
# ---------------------------------------------------------------------------

class TemporalGeoOutput(BaseModel):
    photo_timestamp: Optional[str] = None
    claim_submission_time: Optional[str] = None
    policy_start_date: Optional[str] = None
    timestamp_before_policy: bool = False
    photo_gps: Optional[Dict[str, float]] = None
    registered_region: Optional[str] = None
    geo_mismatch: bool = False
    flags: List[RiskFlag] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Multi-Agent outputs
# ---------------------------------------------------------------------------

class AgentVerdict(BaseModel):
    agent_name: str
    summary: str
    score: float  # 0-1, agent's own confidence in claim validity (semantics vary per agent, documented in prompt)
    flags: List[RiskFlag] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)


class ChainOfEvidenceItem(BaseModel):
    source: str  # e.g. "image_2", "video", "metadata"
    observation: str


class PerImageVerdictSummary(BaseModel):
    image_path: str
    image_authenticity_score: float
    ela_manipulation_score: float
    ai_generation_probability: float
    lighting_consistency_score: float
    notes: List[str] = Field(default_factory=list)
    fraud_verdict: str = "clean"        # "clean" | "suspicious" | "likely_manipulated"
    fraud_headline: str = ""
    fraud_evidence: List[dict] = Field(default_factory=list)  # list of EvidenceItem-shaped dicts


class FinalVerdict(BaseModel):
    claim_id: str
    claim_status: ClaimStatus
    severity: Severity
    risk_flags: List[RiskFlag]

    authenticity_score: float
    ownership_score: float
    possession_score: float
    damage_liveness_score: float
    evidence_coverage_score: float
    claimant_risk_score: float
    fraud_probability: float
    overall_claim_trust_score: float

    chain_of_evidence: List[ChainOfEvidenceItem]
    final_justification: str
    requires_manual_review: bool
    agent_verdicts: List[AgentVerdict]

    per_image_summary: List[PerImageVerdictSummary] = Field(default_factory=list)
    fraud_network_duplicate_claim_ids: List[str] = Field(default_factory=list)
    fraud_network_shared_identifier_claim_ids: List[str] = Field(default_factory=list)

    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Claim submission / record
# ---------------------------------------------------------------------------

class ClaimSubmission(BaseModel):
    user_id: str
    claim_object: ClaimObjectType
    user_claim: str
    user_provided_model: Optional[str] = None
    user_provided_serial: Optional[str] = None
    user_provided_plate: Optional[str] = None
    user_provided_vin: Optional[str] = None
    policy_start_date: Optional[str] = None
    registered_region: Optional[str] = None


class ClaimRecord(BaseModel):
    claim_id: str
    submission: ClaimSubmission
    image_paths: List[str] = Field(default_factory=list)
    video_path: Optional[str] = None
    challenge_code: Optional[str] = None
    status: str = "pending"  # pending -> processing -> completed
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    verdict: Optional[FinalVerdict] = None
