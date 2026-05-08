"""State schema for the LangGraph campaign pipeline."""

from typing import Optional

from typing_extensions import TypedDict


class CampaignState(TypedDict, total=False):
    # ── Input fields ─────────────────────────────────────────
    user_id: str
    city: Optional[str]
    state: Optional[str]
    source: str  # "dashboard" | "genie"
    properties_input: Optional[list[dict]]  # dashboard — pre-selected properties

    # ── Intermediate fields ──────────────────────────────────
    user_profile: Optional[dict]
    browsing_context: Optional[list[dict]]

    # ── Genie input fields ─────────────────────────────────────
    genie_query: Optional[str]  # natural language query
    genie_conversation_id: Optional[str]  # for follow-up queries

    # ── Genie output fields ────────────────────────────────────
    genie_raw_result: Optional[dict]  # raw columns+rows from Genie
    genie_conversation_id_out: Optional[str]  # returned conversation_id
    genie_message_id: Optional[str]  # returned message_id

    # ── Output fields ────────────────────────────────────────
    generated_email: Optional[dict]  # {subject, html, plain_text, raw}
    error: Optional[str]
