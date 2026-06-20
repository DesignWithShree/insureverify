"""
Lightweight JSON-file-based claims store.

Deliberately not a "real" database (Postgres/Mongo) to keep the platform
zero-config and runnable with `python main.py` — no DB server to install.
Each claim is stored as its own JSON file under data/claims_db/, which also
makes the system trivially auditable (you can literally open and read any
claim's full record and verdict).

For a production deployment, swap this module's functions for real DB calls
(e.g. SQLAlchemy + Postgres) — the function signatures are the seam to do
that without touching any stage code, since every stage only depends on the
schemas in core/schemas.py, not on this storage layer directly.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List, Optional

from app.core.schemas import ClaimRecord

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "claims_db"
DB_DIR.mkdir(parents=True, exist_ok=True)


def _claim_path(claim_id: str) -> Path:
    return DB_DIR / f"{claim_id}.json"


def save_claim(claim: ClaimRecord) -> None:
    path = _claim_path(claim.claim_id)
    with open(path, "w") as f:
        f.write(claim.model_dump_json(indent=2))


def load_claim(claim_id: str) -> Optional[ClaimRecord]:
    path = _claim_path(claim_id)
    if not path.exists():
        return None
    with open(path, "r") as f:
        data = json.load(f)
    return ClaimRecord(**data)


def list_all_claims() -> List[ClaimRecord]:
    claims = []
    for path in DB_DIR.glob("*.json"):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            claims.append(ClaimRecord(**data))
        except Exception:
            continue
    return sorted(claims, key=lambda c: c.created_at, reverse=True)


def list_claims_excluding(claim_id: str) -> List[ClaimRecord]:
    return [c for c in list_all_claims() if c.claim_id != claim_id]
