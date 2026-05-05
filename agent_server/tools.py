import json
import logging

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from langchain_core.tools import tool

from agent_server.config import CATALOG, SCHEMA, SQL_WAREHOUSE_ID

logger = logging.getLogger(__name__)

# Service principal workspace client for SQL queries
_sp_client = WorkspaceClient()


def _execute_sql(query: str) -> list[dict]:
    """Execute a SQL query against the configured warehouse and return results as list of dicts."""
    response = _sp_client.statement_execution.execute_statement(
        statement=query,
        warehouse_id=SQL_WAREHOUSE_ID,
        wait_timeout="30s",
    )
    if response.status.state != StatementState.SUCCEEDED:
        error_msg = response.status.error.message if response.status.error else "Unknown error"
        raise RuntimeError(f"SQL execution failed: {error_msg}")

    if not response.result or not response.result.data_array:
        return []

    columns = [col.name for col in response.manifest.schema.columns]
    rows = []
    for row_data in response.result.data_array:
        rows.append(dict(zip(columns, row_data)))
    return rows


@tool
def get_user_profile(user_id: str) -> str:
    """Fetch a user's profile from the Xome users table.

    Args:
        user_id: The UUID of the user to look up.

    Returns:
        JSON string with user profile data including preferences, budget, and segment.
    """
    query = f"""
    SELECT user_id, first_name, last_name, email, phone,
           preferred_city, preferred_state, budget_min, budget_max,
           preferred_property_type, preferred_beds_min,
           signup_date, is_active, user_segment
    FROM {CATALOG}.{SCHEMA}.users
    WHERE user_id = '{user_id}'
    LIMIT 1
    """
    results = _execute_sql(query)
    if not results:
        return json.dumps({"error": f"No user found with user_id: {user_id}"})
    return json.dumps(results[0])


@tool
def get_recommendations(user_id: str, city: str = None, state: str = None, limit: int = 20) -> str:
    """Fetch recommended properties for a user from the Xome recommendations table.

    This is the ONLY source for campaign properties. Returns recommendations joined
    with property details, sorted by recommendation score.

    Args:
        user_id: The UUID of the user.
        city: Optional city filter for recommendations.
        state: Optional state filter for recommendations.
        limit: Maximum number of recommendations to return (default 20).

    Returns:
        JSON string with recommended properties including scores and reasons.
    """
    where_clauses = [
        f"r.user_id = '{user_id}'",
        "r.is_active = true",
    ]
    if city:
        where_clauses.append(f"p.city = '{city}'")
    if state:
        where_clauses.append(f"p.state = '{state}'")

    where_str = " AND ".join(where_clauses)

    query = f"""
    SELECT r.recommendation_id, r.recommendation_score, r.recommendation_reason,
           r.generated_at,
           p.property_id, p.address, p.city, p.state, p.zip_code,
           p.price, p.beds, p.baths, p.sqft, p.property_type,
           p.year_built, p.school_rating, p.neighborhood,
           p.listing_status, p.days_on_market,
           p.auction_date, p.auction_start_price,
           p.hoa_fee, p.description
    FROM {CATALOG}.{SCHEMA}.recommendations r
    JOIN {CATALOG}.{SCHEMA}.properties p ON r.property_id = p.property_id
    WHERE {where_str}
    ORDER BY r.recommendation_score DESC
    LIMIT {limit}
    """
    results = _execute_sql(query)
    if not results:
        return json.dumps({"error": f"No recommendations found for user_id: {user_id}", "count": 0})
    return json.dumps({"count": len(results), "recommendations": results})


@tool
def get_browsing_context(user_id: str) -> str:
    """Fetch recent browsing activity for a user for personalization context.

    This data is for personalization ONLY — it must NOT be used to source campaign properties.

    Args:
        user_id: The UUID of the user.

    Returns:
        JSON string with recent browsing activity including property details.
    """
    query = f"""
    SELECT b.activity_type, b.activity_timestamp, b.session_duration_seconds,
           b.search_query, b.device_type, b.referral_source,
           p.address, p.city, p.state, p.price, p.property_type,
           p.beds, p.neighborhood
    FROM {CATALOG}.{SCHEMA}.browsing_activity b
    JOIN {CATALOG}.{SCHEMA}.properties p ON b.property_id = p.property_id
    WHERE b.user_id = '{user_id}'
    ORDER BY b.activity_timestamp DESC
    LIMIT 20
    """
    results = _execute_sql(query)
    if not results:
        return json.dumps({"browsing_activity": [], "summary": "No recent browsing activity found."})

    # Build a summary
    activity_types = {}
    cities = set()
    property_types = set()
    for r in results:
        act = r.get("activity_type", "unknown")
        activity_types[act] = activity_types.get(act, 0) + 1
        if r.get("city"):
            cities.add(r["city"])
        if r.get("property_type"):
            property_types.add(r["property_type"])

    summary = (
        f"User has {len(results)} recent activities: "
        + ", ".join(f"{count} {atype}" for atype, count in activity_types.items())
        + f". Browsed in cities: {', '.join(cities)}."
        + f" Property types viewed: {', '.join(property_types)}."
    )

    return json.dumps({"browsing_activity": results, "summary": summary})
