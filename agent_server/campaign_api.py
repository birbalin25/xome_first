"""REST API router for the campaign dashboard UI."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_server.tools import _execute_sql

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/campaign", tags=["campaign"])


# ── Pydantic request/response models ──────────────────────────────────────────


class GenieQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


class ListingsRequest(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    listing_count: int = 10


class GenerateEmailRequest(BaseModel):
    user_id: str
    properties: list[dict]
    user_profile: Optional[dict] = None


class SaveEmailRequest(BaseModel):
    user_id: str
    subject: str
    html: str
    plain_text: str
    properties: list[dict] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/filters")
async def get_filters():
    """Return distinct filter values from the database."""
    try:
        cities = _execute_sql("SELECT DISTINCT city FROM properties ORDER BY city")
        states = _execute_sql("SELECT DISTINCT state FROM properties ORDER BY state")
        property_types = _execute_sql(
            "SELECT DISTINCT property_type FROM properties ORDER BY property_type"
        )
        segments = _execute_sql(
            "SELECT DISTINCT user_segment FROM users ORDER BY user_segment"
        )
        prices = _execute_sql(
            "SELECT MIN(price) as min_price, MAX(price) as max_price FROM properties"
        )

        return {
            "cities": [r["city"] for r in cities if r.get("city")],
            "states": [r["state"] for r in states if r.get("state")],
            "property_types": [r["property_type"] for r in property_types if r.get("property_type")],
            "segments": [r["user_segment"] for r in segments if r.get("user_segment")],
            "price_range": {
                "min": float(prices[0]["min_price"]) if prices else 0,
                "max": float(prices[0]["max_price"]) if prices else 5000000,
            },
        }
    except Exception as e:
        logger.exception("Failed to fetch filters")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/genie-query")
async def genie_query(req: GenieQueryRequest):
    """Query Genie Spaces for user discovery via natural language."""
    from agent_server.graph import campaign_graph

    try:
        invoke_input: dict = {
            "source": "genie",
            "genie_query": req.query,
        }
        if req.conversation_id:
            invoke_input["genie_conversation_id"] = req.conversation_id

        result = await campaign_graph.ainvoke(invoke_input)

        raw = result.get("genie_raw_result") or {}

        if result.get("error"):
            return {
                "columns": raw.get("columns", []),
                "rows": raw.get("rows", []),
                "description": raw.get("description", ""),
                "sql": raw.get("sql", ""),
                "conversation_id": result.get("genie_conversation_id_out"),
                "message_id": result.get("genie_message_id"),
                "error": result["error"],
            }

        return {
            "columns": raw.get("columns", []),
            "rows": raw.get("rows", []),
            "description": raw.get("description", ""),
            "sql": raw.get("sql", ""),
            "conversation_id": result.get("genie_conversation_id_out"),
            "message_id": result.get("genie_message_id"),
        }
    except Exception as e:
        logger.exception("Genie query failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}")
async def get_property(property_id: str):
    """Return full details for a single property."""
    query = f"""
    SELECT property_id, address, city, state, zip_code,
           price, beds, baths, sqft, property_type,
           year_built, school_rating, neighborhood,
           listing_status, days_on_market,
           auction_date, auction_start_price,
           hoa_fee, description, image_url
    FROM properties
    WHERE property_id = '{property_id}'
    LIMIT 1
    """
    try:
        rows = _execute_sql(query)
        if not rows:
            raise HTTPException(status_code=404, detail="Property not found")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch property")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    """Return full profile for a single user."""
    query = f"""
    SELECT user_id, first_name, last_name, email, phone,
           preferred_city, preferred_state, budget_min, budget_max,
           preferred_property_type, preferred_beds_min,
           signup_date, is_active, user_segment
    FROM users
    WHERE user_id = '{user_id}'
    LIMIT 1
    """
    try:
        rows = _execute_sql(query)
        if not rows:
            raise HTTPException(status_code=404, detail="User not found")
        return rows[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch user profile")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/listings")
async def get_user_listings(user_id: str, req: ListingsRequest):
    """Return top 5 recommended properties for a user."""
    where = [f"r.user_id = '{user_id}'", "r.is_active = true"]
    if req.city:
        where.append(f"p.city = '{req.city}'")
    if req.state:
        where.append(f"p.state = '{req.state}'")
    where_str = " AND ".join(where)

    query = f"""
    SELECT r.recommendation_id, r.recommendation_score, r.recommendation_reason,
           r.generated_at,
           p.property_id, p.address, p.city, p.state, p.zip_code,
           p.price, p.beds, p.baths, p.sqft, p.property_type,
           p.year_built, p.school_rating, p.neighborhood,
           p.listing_status, p.days_on_market,
           p.auction_date, p.auction_start_price,
           p.hoa_fee, p.description, p.image_url,
           ct.campaign_sent_date
    FROM recommendations r
    JOIN properties p ON r.property_id = p.property_id
    LEFT JOIN (
        SELECT user_id, property_id, MAX(campaign_date) AS campaign_sent_date
        FROM campaign_tracking
        WHERE campaign_status = true
        GROUP BY user_id, property_id
    ) ct
        ON ct.user_id = r.user_id
        AND ct.property_id = p.property_id
    WHERE {where_str}
    ORDER BY r.recommendation_score DESC
    LIMIT {min(max(req.listing_count, 1), 30)}
    """
    try:
        rows = _execute_sql(query)
        return {"properties": rows}
    except Exception as e:
        logger.exception("Failed to fetch listings")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-email")
async def generate_email_endpoint(req: GenerateEmailRequest):
    """Generate a campaign email for the given user + properties via LangGraph."""
    from agent_server.graph import campaign_graph

    try:
        invoke_input: dict = {
            "user_id": req.user_id,
            "properties_input": req.properties,
            "source": "dashboard",
        }
        if req.user_profile:
            invoke_input["user_profile"] = req.user_profile
        result = await campaign_graph.ainvoke(invoke_input)

        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])

        return result.get("generated_email", {})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate email")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-email")
async def save_email(req: SaveEmailRequest):
    """Save the generated email to Lakebase and track campaign sends."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"campaign_{req.user_id}_{timestamp}.txt"

    try:
        # Save email content to Lakebase
        escaped_subject = req.subject.replace("'", "''")
        escaped_html = req.html.replace("'", "''")
        escaped_plain = req.plain_text.replace("'", "''")
        _execute_sql(f"""
            INSERT INTO campaign_emails (user_id, filename, subject, html_body, plain_text, saved_at)
            VALUES ('{req.user_id}', '{filename}', '{escaped_subject}',
                    '{escaped_html}', '{escaped_plain}', NOW())
        """)

        # Insert campaign tracking rows for each property
        if req.properties:
            value_rows = []
            for prop in req.properties:
                pid = prop.get("property_id", "")
                rid = prop.get("recommendation_id", "")
                value_rows.append(
                    f"('{req.user_id}', '{pid}', '{rid}', CURRENT_DATE, true)"
                )
            insert_sql = (
                f"INSERT INTO campaign_tracking "
                f"(user_id, property_id, recommendation_id, campaign_date, campaign_status) "
                f"VALUES {', '.join(value_rows)}"
            )
            _execute_sql(insert_sql)

        saved_path = f"lakebase://xome/campaign_emails/{filename}"
        return {"path": saved_path, "filename": filename}
    except Exception as e:
        logger.exception("Failed to save email")
        raise HTTPException(status_code=500, detail=str(e))
