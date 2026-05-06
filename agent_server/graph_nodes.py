"""Node functions for the LangGraph campaign pipeline."""

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent_server.email_generator import generate_campaign_email, parse_email_response
from agent_server.graph_state import CampaignState
from agent_server.prompts import EXTRACTION_PROMPT
from agent_server.tools import _execute_sql

logger = logging.getLogger(__name__)


# ── Node: process_input ──────────────────────────────────────────────────────


async def process_input(state: CampaignState) -> dict:
    """Extract user_id from the input and fetch the user profile.

    Dashboard: user_id is provided directly.
    Chat: parse raw_message via regex, then LLM fallback.
    """
    source = state.get("source", "dashboard")
    user_id = state.get("user_id")
    city = state.get("city")
    st = state.get("state")

    # Chat path: extract user_id from raw_message
    if source == "chat" and not user_id:
        raw = state.get("raw_message", "")
        if not raw:
            return {"error": "No message provided."}

        # Regex extraction — try USER_NNN format, then UUID format
        id_match = re.search(r"USER_\d+", raw, re.IGNORECASE)
        if id_match:
            user_id = id_match.group(0).upper()
        else:
            uuid_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw, re.IGNORECASE)
            if uuid_match:
                user_id = uuid_match.group(0).lower()

        # Try to extract city from message (simple heuristic)
        if not city:
            city_match = re.search(r"\bin\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", raw)
            if city_match:
                city = city_match.group(1)

        # LLM fallback if no user_id found via regex
        if not user_id:
            try:
                from agent_server.agent import get_llm

                llm = get_llm()
                prompt = EXTRACTION_PROMPT.format(message=raw)
                resp = await llm.ainvoke([HumanMessage(content=prompt)])
                parsed = json.loads(resp.content.strip())
                user_id = parsed.get("user_id")
                if not city:
                    city = parsed.get("city")
                if not st:
                    st = parsed.get("state")
            except Exception:
                logger.exception("LLM extraction fallback failed")

        if not user_id:
            return {"error": "Could not extract a user ID from your message. Please include a user ID (e.g. USER_001 or a UUID)."}

    if not user_id:
        return {"error": "No user_id provided."}

    # Skip DB query if user_profile was provided by the frontend (dashboard path)
    existing_profile = state.get("user_profile")
    if existing_profile:
        result: dict = {"user_id": user_id}
    else:
        # Fetch user profile from DB (chat path)
        profile_rows = _execute_sql(f"""
            SELECT user_id, first_name, last_name, email, phone,
                   preferred_city, preferred_state, budget_min, budget_max,
                   preferred_property_type, preferred_beds_min,
                   signup_date, is_active, user_segment
            FROM users
            WHERE user_id = '{user_id}'
            LIMIT 1
        """)

        if not profile_rows:
            return {"error": f"User {user_id} not found."}

        result = {"user_id": user_id, "user_profile": profile_rows[0]}
    if city:
        result["city"] = city
    if st:
        result["state"] = st
    return result


# ── Node: retrieve_candidates ────────────────────────────────────────────────


async def retrieve_candidates(state: CampaignState) -> dict:
    """Fetch recommended properties from the database.

    Dashboard with properties_input: skip DB query, use provided properties.
    Chat: full DB query with optional city/state filter.
    """
    if state.get("error"):
        return {}

    # Dashboard path: use pre-selected properties
    props_input = state.get("properties_input")
    if props_input:
        return {"candidates": props_input}

    # Chat path: query recommendations from DB
    user_id = state["user_id"]
    where = [f"r.user_id = '{user_id}'", "r.is_active = true"]
    if state.get("city"):
        where.append(f"p.city = '{state['city']}'")
    if state.get("state"):
        where.append(f"p.state = '{state['state']}'")
    where_str = " AND ".join(where)

    query = f"""
    SELECT r.recommendation_id, r.recommendation_score, r.recommendation_reason,
           r.generated_at,
           p.property_id, p.address, p.city, p.state, p.zip_code,
           p.price, p.beds, p.baths, p.sqft, p.property_type,
           p.year_built, p.school_rating, p.neighborhood,
           p.listing_status, p.days_on_market,
           p.auction_date, p.auction_start_price,
           p.hoa_fee, p.description, p.image_url
    FROM recommendations r
    JOIN properties p ON r.property_id = p.property_id
    WHERE {where_str}
    ORDER BY r.recommendation_score DESC
    LIMIT 5
    """
    rows = _execute_sql(query)
    if not rows:
        return {"error": f"No recommended properties found for user {user_id}."}
    return {"candidates": rows}


# ── Node: rank_and_select ────────────────────────────────────────────────────


async def rank_and_select(state: CampaignState) -> dict:
    """Sort candidates by recommendation score and pick top 5.

    Dashboard with properties_input: pass-through (already selected by UI).
    Chat: full sort.
    """
    if state.get("error"):
        return {}

    candidates = state.get("candidates", [])
    if not candidates:
        return {"error": "No candidate properties to rank."}

    # Dashboard path: properties_input already curated
    if state.get("properties_input"):
        return {"selected_properties": candidates}

    # Chat path: sort by score descending, take top 5
    def score_key(p: dict) -> float:
        try:
            return float(p.get("recommendation_score", 0))
        except (ValueError, TypeError):
            return 0.0

    sorted_props = sorted(candidates, key=score_key, reverse=True)[:5]
    return {"selected_properties": sorted_props}


# ── Node: enrich_context ────────────────────────────────────────────────────


async def enrich_context(state: CampaignState) -> dict:
    """Fetch last 20 browsing activities for personalization context."""
    if state.get("error"):
        return {}

    user_id = state["user_id"]
    browsing_rows = _execute_sql(f"""
        SELECT b.activity_type, b.activity_timestamp, b.session_duration_seconds,
               b.search_query, b.device_type, b.referral_source,
               p.address, p.city, p.state, p.price, p.property_type,
               p.beds, p.neighborhood
        FROM browsing_activity b
        JOIN properties p ON b.property_id = p.property_id
        WHERE b.user_id = '{user_id}'
        ORDER BY b.activity_timestamp DESC
        LIMIT 20
    """)
    return {"browsing_context": browsing_rows}


# ── Node: generate_email ────────────────────────────────────────────────────


async def generate_email(state: CampaignState) -> dict:
    """Call the LLM to generate a campaign email."""
    if state.get("error"):
        return {}

    from agent_server.agent import get_llm

    profile = state["user_profile"]
    properties = state.get("selected_properties", [])
    browsing = state.get("browsing_context", [])

    llm = get_llm()
    email_result = await generate_campaign_email(llm, profile, properties, browsing)

    result: dict = {"generated_email": email_result}

    # Chat path: also build a chat_response summary
    if state.get("source") == "chat":
        first_name = profile.get("first_name", "the user")
        subject = email_result.get("subject", "N/A")
        n_props = len(properties)
        result["chat_response"] = (
            f"I've generated a campaign email for {first_name} "
            f"featuring {n_props} recommended propert{'y' if n_props == 1 else 'ies'}.\n\n"
            f"**Subject:** {subject}"
        )

    return result


# ── Node: handle_error ──────────────────────────────────────────────────────


async def handle_error(state: CampaignState) -> dict:
    """Format the error for the appropriate output channel."""
    error = state.get("error", "An unknown error occurred.")

    result: dict = {"error": error}
    if state.get("source") == "chat":
        result["chat_response"] = f"Sorry, I couldn't complete that request: {error}"
    return result
