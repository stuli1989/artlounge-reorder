"""Party classification API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import get_current_user, require_role
from api.database import get_db

router = APIRouter(tags=["parties"])

VALID_CHANNELS = {"supplier", "wholesale", "online", "store", "internal", "ignore"}


class ClassifyRequest(BaseModel):
    name: str
    channel: str


@router.get("/parties")
def list_all_parties(channel: str = None, search: str = None, user: dict = Depends(get_current_user)):
    """List all parties with their current channel."""
    with get_db() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT p.tally_name AS name, p.tally_parent AS party_group,
                       p.channel, p.created_at, p.classified_at
                FROM parties p
            """
            conditions, params = [], []
            if channel:
                conditions.append("p.channel = %s")
                params.append(channel)
            if search:
                conditions.append("p.tally_name ILIKE %s")
                params.append(f"%{search}%")
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY p.tally_name"
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/parties/unclassified")
def list_unclassified(user: dict = Depends(get_current_user)):
    """List parties needing channel classification."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.tally_name AS name, p.tally_parent AS party_group, p.created_at
                FROM parties p
                WHERE p.channel = 'unclassified'
                ORDER BY p.tally_name
            """)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/parties/classify")
def classify_party(req: ClassifyRequest, user: dict = Depends(require_role("purchaser"))):
    """Classify a party's channel and recompute affected SKU metrics."""
    if req.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid channel '{req.channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE parties SET channel = %s, classified_at = NOW()
                WHERE tally_name = %s
            """, (req.channel, req.name))

            if cur.rowcount == 0:
                raise HTTPException(404, f"Party '{req.name}' not found")

        conn.commit()

        # Trigger targeted recompute for affected SKUs
        from engine.targeted_recompute import recompute_skus_for_party
        recompute_result = recompute_skus_for_party(conn, req.name)

    return {
        "success": True,
        "party": req.name,
        "channel": req.channel,
        **recompute_result,
    }
