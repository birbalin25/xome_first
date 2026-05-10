"""Node functions for the LangGraph campaign pipeline."""

import logging

import mlflow

from agent_server.email_generator import generate_campaign_email
from agent_server.genie_client import query_genie
from agent_server.graph_state import CampaignState
from agent_server.tools import _execute_sql

logger = logging.getLogger(__name__)


# ── Node: enrich_context ────────────────────────────────────────────────────


@mlflow.trace(name="enrich_context", span_type="tool")
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


@mlflow.trace(name="generate_email", span_type="chain")
async def generate_email(state: CampaignState) -> dict:
    """Call the LLM to generate a campaign email."""
    if state.get("error"):
        return {}

    if not state.get("user_id"):
        return {"error": "No user_id provided."}
    if not state.get("user_profile"):
        return {"error": "No user_profile provided."}
    if not state.get("properties_input"):
        return {"error": "No properties provided."}

    from agent_server.agent import get_llm

    profile = state["user_profile"]
    properties = state["properties_input"]
    browsing = state.get("browsing_context", [])
    previous_email = state.get("previous_email")

    llm = get_llm()
    email_result = await generate_campaign_email(llm, profile, properties, browsing, previous_email)

    return {"generated_email": email_result}


# ── Node: query_genie ──────────────────────────────────────────────────────


@mlflow.trace(name="query_genie", span_type="tool")
async def query_genie_node(state: CampaignState) -> dict:
    """Query Genie Spaces API with a natural language query.

    Supports both new conversations and follow-ups.
    """
    genie_query_text = state.get("genie_query", "")
    conversation_id = state.get("genie_conversation_id")

    if not genie_query_text:
        return {"error": "No Genie query provided."}

    try:
        result = await query_genie(
            query=genie_query_text,
            conversation_id=conversation_id,
        )
        logger.debug(
            "Genie returned %d columns, %d rows",
            len(result.get("columns", [])),
            len(result.get("rows", [])),
        )
        return {
            "genie_raw_result": {
                "columns": result["columns"],
                "rows": result["rows"],
                "description": result.get("description", ""),
                "sql": result.get("sql", ""),
            },
            "genie_conversation_id_out": result["conversation_id"],
            "genie_message_id": result["message_id"],
        }
    except TimeoutError as e:
        logger.exception("Genie query timed out")
        return {"error": f"Genie query timed out: {e}"}
    except Exception as e:
        logger.exception("Genie query failed")
        return {"error": f"Genie query failed: {e}"}


# ── Node: handle_error ──────────────────────────────────────────────────────


async def handle_error(state: CampaignState) -> dict:
    """Pass through the error state."""
    return {"error": state.get("error", "An unknown error occurred.")}
