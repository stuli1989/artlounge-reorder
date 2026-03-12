"""Party classification API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.database import get_db

router = APIRouter(tags=["parties"])

VALID_CHANNELS = {"supplier", "wholesale", "online", "store", "internal", "ignore"}


class ClassifyRequest(BaseModel):
    tally_name: str
    channel: str


@router.get("/parties/unclassified")
def list_unclassified():
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
def classify_party(req: ClassifyRequest):
    """Classify a party's channel and update its transactions."""
    if req.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid channel '{req.channel}'. Must be one of: {', '.join(sorted(VALID_CHANNELS))}")

    with get_db() as conn:
        with conn.cursor() as cur:
            # Update party
            cur.execute("""
                UPDATE parties SET channel = %s, classified_at = NOW()
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

    return {"success": True, "party": req.tally_name, "channel": req.channel,
            "transactions_updated": txn_updated}
