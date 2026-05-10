"""Shared email generation logic used by both the LangGraph agent and the campaign REST API."""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent_server.generate_email_prompt import EMAIL_GENERATION_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_properties_section(properties: list[dict]) -> str:
    """Format a list of property dicts into the prompt's properties section."""
    if not properties:
        return "No properties available."

    lines = []
    for i, prop in enumerate(properties, 1):
        status = prop.get("listing_status", "active").upper()
        line = f"""
**Property {i}: {prop.get('address', 'N/A')}** (property_id: {prop.get('property_id', 'N/A')})
- Location: {prop.get('neighborhood', 'N/A')}, {prop.get('city', 'N/A')}, {prop.get('state', 'N/A')} {prop.get('zip_code', '')}
- Price: ${int(float(prop.get('price', 0))):,}
- Details: {prop.get('beds', 'N/A')} beds / {prop.get('baths', 'N/A')} baths / {int(float(prop.get('sqft', 0))):,} sqft
- Type: {prop.get('property_type', 'N/A')} | Year Built: {prop.get('year_built', 'N/A')}
- School Rating: {prop.get('school_rating', 'N/A')}/10
- Status: [{status}]
- Days on Market: {prop.get('days_on_market', 'N/A')}
- HOA Fee: ${prop.get('hoa_fee', 0)}/mo"""

        if status == "AUCTION":
            line += f"""
- AUCTION DATE: {prop.get('auction_date', 'TBD')}
- AUCTION STARTING PRICE: ${int(float(prop.get('auction_start_price', 0))):,}"""

        line += f"""
- Recommendation Score: {prop.get('recommendation_score', 'N/A')}
- Why Recommended: {prop.get('recommendation_reason', 'N/A')}
- Description: {prop.get('description', 'N/A')}"""
        lines.append(line)

    return "\n".join(lines)


def build_browsing_section(browsing: list[dict]) -> str:
    """Format browsing activity dicts into the prompt's browsing section."""
    if not browsing:
        return "No recent browsing activity."

    lines = []
    for b in browsing[:10]:
        lines.append(
            f"- [{b.get('activity_type', 'unknown')}] {b.get('address', 'N/A')} in {b.get('city', 'N/A')} "
            f"({b.get('property_type', 'N/A')}, ${int(float(b.get('price', 0))):,}) — {b.get('activity_timestamp', 'N/A')}"
        )
    return "\n".join(lines)


def build_previous_email_section(previous_email: dict | None) -> str:
    """Format the most recently sent email as context for the LLM."""
    if not previous_email:
        return ""

    sent_date = previous_email.get("saved_at", "unknown")
    return (
        "\n\n## Previously Sent Email (for context — vary tone and phrasing, do NOT repeat verbatim)\n"
        f"- Sent Date: {sent_date}\n"
        f"- Subject: {previous_email.get('subject', '')}\n"
        f"- Body:\n{previous_email.get('plain_text', '')}"
    )


def format_email_prompt(
    profile: dict, properties: list[dict], browsing: list[dict], previous_email: dict | None = None
) -> str:
    """Build the full email-generation prompt from profile, properties, and browsing data."""
    properties_section = build_properties_section(properties)
    browsing_section = build_browsing_section(browsing)
    previous_email_section = build_previous_email_section(previous_email)

    prompt = EMAIL_GENERATION_PROMPT.format(
        first_name=profile.get("first_name", ""),
        last_name=profile.get("last_name", ""),
        email=profile.get("email", ""),
        user_segment=profile.get("user_segment", ""),
        preferred_city=profile.get("preferred_city", ""),
        preferred_state=profile.get("preferred_state", ""),
        budget_min=int(float(profile.get("budget_min", 0))),
        budget_max=int(float(profile.get("budget_max", 0))),
        preferred_property_type=profile.get("preferred_property_type", ""),
        preferred_beds_min=profile.get("preferred_beds_min", ""),
        properties_section=properties_section,
        browsing_section=browsing_section,
    )

    return prompt + previous_email_section


def parse_email_response(raw: str) -> dict:
    """Parse the LLM's response into subject, html, and plain_text sections."""
    result = {"subject": "", "html": "", "plain_text": "", "raw": raw}

    # Extract SUBJECT
    subject_match = re.search(r"SUBJECT:\s*(.+?)(?:\n|$)", raw)
    if subject_match:
        result["subject"] = subject_match.group(1).strip()

    # Extract HTML section
    html_match = re.search(r"HTML:\s*\n(.*?)(?=\nPLAIN TEXT:|\Z)", raw, re.DOTALL)
    if html_match:
        result["html"] = html_match.group(1).strip()

    # Extract PLAIN TEXT section
    plain_match = re.search(r"PLAIN TEXT:\s*\n(.*)", raw, re.DOTALL)
    if plain_match:
        result["plain_text"] = plain_match.group(1).strip()

    return result


async def generate_campaign_email(
    llm, profile: dict, properties: list[dict], browsing: list[dict], previous_email: dict | None = None
) -> dict:
    """Invoke the LLM to generate a campaign email. Returns parsed sections."""
    prompt = format_email_prompt(profile, properties, browsing, previous_email)

    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return parse_email_response(response.content)
