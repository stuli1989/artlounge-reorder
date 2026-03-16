"""Party classification API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.auth import get_current_user, require_role
from api.database import get_db

router = APIRouter(tags=["parties"])

VALID_CHANNELS = {"supplier", "wholesale", "online", "store", "internal", "ignore"}


class ClassifyRequest(BaseModel):
    tally_name: str
    channel: str


@router.get("/parties")
def list_all_parties(channel: str = None, search: str = None, user: dict = Depends(get_current_user)):
    """List all parties with their current channel and transaction count."""
    with get_db() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT p.tally_name, p.tally_parent, p.channel, p.created_at,
                       p.classified_at, COUNT(t.id) AS transaction_count
                FROM parties p
                LEFT JOIN transactions t ON t.party_name = p.tally_name
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
            sql += " GROUP BY p.id, p.tally_name, p.tally_parent, p.channel, p.created_at, p.classified_at"
            sql += " ORDER BY transaction_count DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/parties/unclassified")
def list_unclassified(user: dict = Depends(get_current_user)):
    """List parties needing channel classification."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.tally_name, p.tally_parent, p.created_at,
                       COUNT(t.id) AS transaction_count
                FROM parties p
                LEFT JOIN transactions t ON t.party_name = p.tally_name
                WHERE p.channel = 'unclassified'
                GROUP BY p.id, p.tally_name, p.tally_parent, p.created_at
                ORDER BY transaction_count DESC
            """)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/parties/classify")
def classify_party(req: ClassifyRequest, user: dict = Depends(require_role("purchaser"))):
    """Classify a party's channel, update transactions, and recompute affected SKU metrics."""
    if req.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid channel '{req.channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Update party with is_manual flag
            cur.execute("""
                UPDATE parties SET channel = %s, classified_at = NOW(), is_manual = TRUE
                WHERE tally_name = %s
            """, (req.channel, req.tally_name))

            if cur.rowcount == 0:
                raise HTTPException(404, f"Party '{req.tally_name}' not found")

            # Update transactions for this party
            cur.execute("""
                UPDATE transactions SET channel = %s
                WHERE party_name = %s
            """, (req.channel, req.tally_name))
            txn_updated = cur.rowcount

        conn.commit()

        # Trigger targeted recompute for affected SKUs
        from engine.targeted_recompute import recompute_skus_for_party
        recompute_result = recompute_skus_for_party(conn, req.tally_name)

    return {
        "success": True,
        "party": req.tally_name,
        "channel": req.channel,
        "transactions_updated": txn_updated,
        **recompute_result,
    }
