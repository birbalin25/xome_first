"""Normalize Genie Spaces query results to canonical UserSummary fields."""

import logging
import re

logger = logging.getLogger(__name__)

# Map common Genie column names (lowercased) to canonical field names
_COLUMN_MAP: dict[str, str] = {
    "userid": "user_id",
    "user_id": "user_id",
    "id": "user_id",
    "firstname": "first_name",
    "first_name": "first_name",
    "lastname": "last_name",
    "last_name": "last_name",
    "name": "name",  # handled specially — split into first_name/last_name
    "email": "email",
    "phone": "phone",
    "preferredcity": "preferred_city",
    "preferred_city": "preferred_city",
    "city": "preferred_city",
    "preferredstate": "preferred_state",
    "preferred_state": "preferred_state",
    "state": "preferred_state",
    "budgetmin": "budget_min",
    "budget_min": "budget_min",
    "budgetmax": "budget_max",
    "budget_max": "budget_max",
    "preferredpropertytype": "preferred_property_type",
    "preferred_property_type": "preferred_property_type",
    "propertytype": "preferred_property_type",
    "property_type": "preferred_property_type",
    "preferredbedsmin": "preferred_beds_min",
    "preferred_beds_min": "preferred_beds_min",
    "signupdate": "signup_date",
    "signup_date": "signup_date",
    "isactive": "is_active",
    "is_active": "is_active",
    "usersegment": "user_segment",
    "user_segment": "user_segment",
    "segment": "user_segment",
    "reccount": "rec_count",
    "rec_count": "rec_count",
    "recommendation_count": "rec_count",
}


def _normalize_column_name(raw: str) -> str:
    """Map a raw column name to a canonical field name."""
    key = re.sub(r"[^a-z0-9_]", "", raw.lower().replace(" ", "_"))
    return _COLUMN_MAP.get(key, raw)


def normalize_genie_to_users(columns: list[dict], rows: list[list]) -> list[dict]:
    """Convert Genie tabular results to a list of user dicts with canonical field names.

    Args:
        columns: List of {"name": "...", "type": "..."} from Genie response.
        rows: 2D list of values (each inner list matches columns order).

    Returns:
        List of dicts with normalized field names.
    """
    if not columns or not rows:
        return []

    col_names = [_normalize_column_name(c["name"]) for c in columns]

    users = []
    for row in rows:
        user = {}
        for i, val in enumerate(row):
            if i < len(col_names):
                field = col_names[i]
                user[field] = val if val is not None else ""
        # Handle "name" → split into first_name / last_name
        if "name" in user and "first_name" not in user:
            parts = str(user["name"]).strip().split(None, 1)
            user["first_name"] = parts[0] if parts else ""
            user["last_name"] = parts[1] if len(parts) > 1 else ""
            del user["name"]

        users.append(user)

    return users


def extract_user_ids(normalized_users: list[dict]) -> list[str]:
    """Extract unique user_id values from normalized user list."""
    seen = set()
    ids = []
    for u in normalized_users:
        uid = u.get("user_id", "")
        if uid and uid not in seen:
            seen.add(uid)
            ids.append(uid)
    return ids
