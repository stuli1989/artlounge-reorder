"""Channel rules CRUD API endpoints."""
import threading
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from api.database import get_db
from api.auth import get_current_user, require_role

router = APIRouter(tags=["channel_rules"])

VALID_RULE_TYPES = {"entity", "sale_order_prefix", "default"}
VALID_CHANNELS = {"supplier", "wholesale", "online", "store", "internal", "ignore", "unclassified"}


class ChannelRuleCreate(BaseModel):
    rule_type: str
    match_value: str
    facility_filter: str | None = None
    channel: str
    priority: int


class ChannelRuleUpdate(BaseModel):
    match_value: str | None = None
    facility_filter: str | None = None
    channel: str | None = None
    priority: int | None = None
    is_active: bool | None = None


def _run_pipeline_background():
    """Spawn a background thread to recompute the full pipeline."""
    def _task():
        try:
            from engine.pipeline import run_computation_pipeline
            with get_db() as conn:
                run_computation_pipeline(conn)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Background pipeline recompute failed: %s", exc)

    t = threading.Thread(target=_task, daemon=True)
    t.start()


@router.get("/channel-rules")
def list_channel_rules(user: dict = Depends(get_current_user)):
    """List all active channel rules, ordered by priority DESC."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM channel_rules
                WHERE is_active = TRUE
                ORDER BY priority DESC
            """)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/channel-rules")
def create_channel_rule(req: ChannelRuleCreate, user: dict = Depends(require_role("admin"))):
    """Create a new channel rule."""
    if req.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(400, f"Invalid rule_type. Must be one of: {', '.join(sorted(VALID_RULE_TYPES))}")
    if req.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid channel. Must be one of: {', '.join(sorted(VALID_CHANNELS))}")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO channel_rules (rule_type, match_value, facility_filter, channel, priority)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
            """, (req.rule_type, req.match_value, req.facility_filter, req.channel, req.priority))
            row = cur.fetchone()
        conn.commit()

    _run_pipeline_background()
    return dict(row)


@router.put("/channel-rules/{rule_id}")
def update_channel_rule(rule_id: int, req: ChannelRuleUpdate, user: dict = Depends(require_role("admin"))):
    """Update an existing channel rule."""
    ALLOWED_COLUMNS = {"match_value", "facility_filter", "channel", "priority", "is_active"}

    sent_fields = req.model_dump(exclude_unset=True)
    if not sent_fields:
        raise HTTPException(400, "No fields to update")

    # Validate channel if provided
    if "channel" in sent_fields and sent_fields["channel"] not in VALID_CHANNELS:
        raise HTTPException(400, f"Invalid channel. Must be one of: {', '.join(sorted(VALID_CHANNELS))}")

    updates = {k: v for k, v in sent_fields.items() if k in ALLOWED_COLUMNS}
    if not updates:
        raise HTTPException(400, "No valid fields to update")

    set_parts = [f"{k} = %s" for k in updates]
    set_parts.append("updated_at = NOW()")
    values = list(updates.values())
    values.append(rule_id)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE channel_rules
                SET {', '.join(set_parts)}
                WHERE id = %s
                RETURNING *
            """, values)
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Channel rule not found")
        conn.commit()

    _run_pipeline_background()
    return dict(row)


@router.delete("/channel-rules/{rule_id}")
def delete_channel_rule(rule_id: int, user: dict = Depends(require_role("admin"))):
    """Soft-delete a channel rule (set is_active=False)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE channel_rules
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = %s AND is_active = TRUE
                RETURNING *
            """, (rule_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Active channel rule not found")
        conn.commit()

    _run_pipeline_background()
    return {"success": True, "id": rule_id}
