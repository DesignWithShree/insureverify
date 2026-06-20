"""
InsureVerify — FastAPI backend entrypoint.

Run with:  uvicorn main:app --reload --port 8000
(see README.md / run instructions for full setup)
"""
from __future__ import annotations
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.schemas import ClaimRecord, ClaimSubmission, ClaimObjectType
from app.core.api_models import (
    CreateClaimRequest, CreateClaimResponse, ClaimListResponse, ClaimSummary,
    ClaimDetailResponse, NetworkClaimRef,
)
from app.db.claims_store import save_claim, load_claim, list_all_claims
from app.stages.stage2_possession import generate_challenge_code
from app.core.pipeline import run_full_pipeline
from app.core.csv_export import append_claim_to_csv, write_claims_csv, claims_to_csv_string
from app.utils.ollama_client import is_ollama_available

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV_PATH = BASE_DIR / "data" / "output.csv"


def _to_url(path: str) -> str:
    """Converts an absolute filesystem path under data/uploads into a
    browser-servable URL path mounted at /uploads."""
    try:
        rel = Path(path).resolve().relative_to(UPLOADS_DIR.resolve())
        return f"/uploads/{rel.as_posix()}"
    except Exception:
        return path

app = FastAPI(title="InsureVerify API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo/local-dev setting; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/api/health")
def health_check():
    from app.utils.ollama_client import FAST_MODE
    return {
        "status": "ok",
        "ollama_available": is_ollama_available(),
        "fast_mode": FAST_MODE,
    }


@app.post("/api/claims", response_model=CreateClaimResponse)
def create_claim(payload: CreateClaimRequest):
    claim_id = f"claim_{uuid.uuid4().hex[:10]}"
    challenge_code = generate_challenge_code(claim_id)

    submission = ClaimSubmission(
        user_id=payload.user_id,
        claim_object=payload.claim_object,
        user_claim=payload.user_claim,
        user_provided_model=payload.user_provided_model,
        user_provided_serial=payload.user_provided_serial,
        user_provided_plate=payload.user_provided_plate,
        user_provided_vin=payload.user_provided_vin,
        policy_start_date=payload.policy_start_date,
        registered_region=payload.registered_region,
    )
    claim = ClaimRecord(
        claim_id=claim_id,
        submission=submission,
        challenge_code=challenge_code,
        status="awaiting_evidence",
    )
    save_claim(claim)

    return CreateClaimResponse(
        claim_id=claim_id,
        challenge_code=challenge_code,
        message=f"Claim created. Please write the code '{challenge_code}' on paper, place it next to the "
                 f"object, and include it in your evidence photos/video.",
    )


@app.post("/api/claims/{claim_id}/evidence")
async def upload_evidence(
    claim_id: str,
    images: List[UploadFile] = File(default=[]),
    video: Optional[UploadFile] = File(default=None),
):
    claim = load_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim_dir = UPLOADS_DIR / claim_id
    claim_dir.mkdir(parents=True, exist_ok=True)

    saved_image_paths = []
    for img in images:
        ext = Path(img.filename).suffix or ".jpg"
        dest = claim_dir / f"img_{uuid.uuid4().hex[:8]}{ext}"
        with open(dest, "wb") as f:
            shutil.copyfileobj(img.file, f)
        saved_image_paths.append(str(dest))

    saved_video_path = None
    if video is not None:
        ext = Path(video.filename).suffix or ".mp4"
        dest = claim_dir / f"video_{uuid.uuid4().hex[:8]}{ext}"
        with open(dest, "wb") as f:
            shutil.copyfileobj(video.file, f)
        saved_video_path = str(dest)

    claim.image_paths.extend(saved_image_paths)
    if saved_video_path:
        claim.video_path = saved_video_path
    claim.status = "evidence_uploaded"
    save_claim(claim)

    return {
        "claim_id": claim_id,
        "images_uploaded": len(saved_image_paths),
        "video_uploaded": saved_video_path is not None,
        "total_images": len(claim.image_paths),
    }


@app.post("/api/claims/{claim_id}/verify", response_model=ClaimDetailResponse)
def verify_claim(
    claim_id: str,
    past_claim_count: int = 0,
    rejected_claim_count: int = 0,
):
    claim = load_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if not claim.image_paths:
        raise HTTPException(status_code=400, detail="No evidence images uploaded yet")

    claim.status = "processing"
    save_claim(claim)

    verdict = run_full_pipeline(
        claim, past_claim_count=past_claim_count, rejected_claim_count=rejected_claim_count,
    )
    claim.verdict = verdict
    claim.status = "completed"

    # Auto-append this claim's row to output.csv BEFORE rewriting image
    # paths to browser-servable URLs below — the CSV should reflect the
    # claim's own filesystem-relative image references, not UI plumbing.
    try:
        append_claim_to_csv(claim, str(OUTPUT_CSV_PATH))
    except Exception as e:
        # CSV export is a side-effect, not the source of truth (the saved
        # claim JSON is) — never fail the verification request over it.
        print(f"[csv_export] failed to append claim {claim_id}: {e}")

    for pi in verdict.per_image_summary:
        pi.image_path = _to_url(pi.image_path)
    save_claim(claim)

    return ClaimDetailResponse(
        claim_id=claim_id, status=claim.status, verdict=verdict,
        image_paths=[_to_url(p) for p in claim.image_paths],
        video_path=_to_url(claim.video_path) if claim.video_path else None,
        challenge_code=claim.challenge_code,
        user_claim=claim.submission.user_claim,
        claim_object=claim.submission.claim_object.value,
    )


@app.get("/api/claims/{claim_id}", response_model=ClaimDetailResponse)
def get_claim(claim_id: str):
    claim = load_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    verdict = claim.verdict
    if verdict:
        for pi in verdict.per_image_summary:
            pi.image_path = _to_url(pi.image_path)
    return ClaimDetailResponse(
        claim_id=claim_id,
        status=claim.status,
        verdict=verdict,
        image_paths=[_to_url(p) for p in claim.image_paths],
        video_path=_to_url(claim.video_path) if claim.video_path else None,
        challenge_code=claim.challenge_code,
        user_claim=claim.submission.user_claim,
        claim_object=claim.submission.claim_object.value,
    )


@app.get("/api/claims/{claim_id}/network/{other_claim_id}", response_model=NetworkClaimRef)
def get_network_claim(claim_id: str, other_claim_id: str):
    """Fetches a minimal reference to another claim flagged by the Fraud
    Network engine (duplicate image / shared identifier), so the UI can
    render a side-by-side comparison."""
    other = load_claim(other_claim_id)
    if not other:
        raise HTTPException(status_code=404, detail="Referenced claim not found")
    return NetworkClaimRef(
        claim_id=other.claim_id,
        user_id=other.submission.user_id,
        claim_object=other.submission.claim_object.value,
        image_paths=[_to_url(p) for p in other.image_paths],
        created_at=other.created_at,
    )


@app.get("/api/claims", response_model=ClaimListResponse)
def list_claims():
    claims = list_all_claims()
    summaries = [
        ClaimSummary(
            claim_id=c.claim_id,
            user_id=c.submission.user_id,
            claim_object=c.submission.claim_object.value,
            status=c.status,
            created_at=c.created_at,
            overall_claim_trust_score=c.verdict.overall_claim_trust_score if c.verdict else None,
            claim_status=c.verdict.claim_status.value if c.verdict else None,
            requires_manual_review=c.verdict.requires_manual_review if c.verdict else None,
        )
        for c in claims
    ]
    return ClaimListResponse(claims=summaries)


@app.post("/api/export/csv")
def export_all_claims_csv():
    """Batch export: regenerates output.csv from ALL claims currently in the
    store (whether or not they've been verified — unverified claims export
    with 'not_enough_information'/'unknown' placeholders rather than being
    skipped, so the CSV always has exactly one row per claim)."""
    claims = list_all_claims()
    write_claims_csv(claims, str(OUTPUT_CSV_PATH))
    return {
        "rows_written": len(claims),
        "output_path": str(OUTPUT_CSV_PATH),
    }


@app.get("/api/export/csv")
def download_claims_csv():
    """Streams the current output.csv as a downloadable file. If it doesn't
    exist yet (no claim has ever been verified), regenerates it first from
    whatever claims currently exist."""
    if not OUTPUT_CSV_PATH.exists():
        claims = list_all_claims()
        write_claims_csv(claims, str(OUTPUT_CSV_PATH))
    return FileResponse(
        path=str(OUTPUT_CSV_PATH),
        media_type="text/csv",
        filename="output.csv",
    )


@app.get("/api/taxonomy")
def get_taxonomy():
    from app.core.taxonomy import OBJECT_PARTS, OBJECT_ISSUES
    return {"parts": OBJECT_PARTS, "issues": OBJECT_ISSUES}
