import json
import logging
from typing import Annotated, AsyncGenerator, Optional, TypedDict

import mlflow
from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks, DatabricksMCPServer, DatabricksMultiServerMCPClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    to_chat_completions_input,
)

from agent_server.config import GENIE_SPACE_ID, LLM_ENDPOINT
from agent_server.prompts import EMAIL_GENERATION_PROMPT, SYSTEM_PROMPT
from agent_server.tools import get_browsing_context, get_recommendations, get_user_profile
from agent_server.utils import (
    get_databricks_host_from_env,
    get_session_id,
    process_agent_astream_events,
)

logger = logging.getLogger(__name__)
mlflow.langchain.autolog()
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
sp_workspace_client = WorkspaceClient()


# --- Sanitized ChatDatabricks for Claude compatibility ---

class _SanitizedChatDatabricks(ChatDatabricks):
    """Strips extra fields (e.g. 'id') from tool message content blocks
    that some LLM APIs reject."""

    @staticmethod
    def _strip_content_ids(messages):
        for msg in messages:
            if isinstance(msg.content, list):
                msg.content = [
                    {k: v for k, v in block.items() if k != "id"}
                    if isinstance(block, dict) else block
                    for block in msg.content
                ]
        return messages

    def _stream(self, messages, *args, **kwargs):
        return super()._stream(self._strip_content_ids(messages), *args, **kwargs)

    async def _astream(self, messages, *args, **kwargs):
        async for chunk in super()._astream(self._strip_content_ids(messages), *args, **kwargs):
            yield chunk


# --- LangGraph State ---

class CampaignState(TypedDict):
    messages: Annotated[list, add_messages]
    user_profile: Optional[dict]
    candidate_properties: Optional[list]
    top_5_properties: Optional[list]
    browsing_context: Optional[list]
    campaign_email: Optional[str]
    error: Optional[str]


# --- LLM instance ---

def get_llm():
    return _SanitizedChatDatabricks(endpoint=LLM_ENDPOINT)


# --- Graph Nodes ---

async def process_input(state: CampaignState) -> dict:
    """Parse user message to extract user_id, fetch user profile."""
    messages = state["messages"]
    user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            break

    if not user_message:
        return {"error": "No user message found.", "messages": [AIMessage(content="I didn't receive a message. Please provide a user_id to generate a campaign email.")]}

    # Use LLM to extract user_id and optional city/state from the message
    llm = get_llm()
    extraction_prompt = f"""Extract the user_id (UUID format) from the following message. Also extract city and state if mentioned.
Return ONLY a JSON object with keys: "user_id", "city" (optional), "state" (optional).
If no valid user_id is found, return {{"error": "no_user_id"}}.

Message: {user_message}"""

    response = await llm.ainvoke([SystemMessage(content="You are a JSON extraction assistant. Return only valid JSON, no markdown."), HumanMessage(content=extraction_prompt)])
    try:
        parsed = json.loads(response.content.strip())
    except json.JSONDecodeError:
        # Try to find JSON in the response
        content = response.content.strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end])
        else:
            return {"error": "Could not parse user_id from your message.", "messages": [AIMessage(content="I couldn't extract a user_id from your message. Please provide a valid user_id (UUID format).")]}

    if "error" in parsed:
        return {"error": parsed["error"], "messages": [AIMessage(content="I couldn't find a valid user_id in your message. Please provide a user_id (UUID format) to generate a campaign email.")]}

    user_id = parsed["user_id"]

    # Fetch user profile
    profile_json = get_user_profile.invoke({"user_id": user_id})
    profile = json.loads(profile_json)

    if "error" in profile:
        return {"error": profile["error"], "messages": [AIMessage(content=f"User not found: {profile['error']}")]}

    # Store city/state from request or fallback to profile preferences
    profile["_request_city"] = parsed.get("city") or profile.get("preferred_city")
    profile["_request_state"] = parsed.get("state") or profile.get("preferred_state")

    return {"user_profile": profile}


async def retrieve_candidates(state: CampaignState) -> dict:
    """Fetch recommended properties from the recommendation table ONLY."""
    profile = state["user_profile"]
    user_id = profile["user_id"]
    city = profile.get("_request_city")
    state_code = profile.get("_request_state")

    result_json = get_recommendations.invoke({
        "user_id": user_id,
        "city": city,
        "state": state_code,
        "limit": 20,
    })
    result = json.loads(result_json)

    if "error" in result:
        return {
            "candidate_properties": [],
            "error": result["error"],
            "messages": [AIMessage(content=f"No recommended properties found for this user in {city}, {state_code}. The recommendation pipeline may need to be run or the user's preferences may not match any available properties.")],
        }

    return {"candidate_properties": result.get("recommendations", [])}


async def rank_and_select(state: CampaignState) -> dict:
    """Sort candidates by recommendation_score and pick top 5."""
    candidates = state.get("candidate_properties", [])

    # Sort by recommendation_score descending
    sorted_candidates = sorted(
        candidates,
        key=lambda x: float(x.get("recommendation_score", 0)),
        reverse=True,
    )

    top_5 = sorted_candidates[:5]
    return {"top_5_properties": top_5}


async def enrich_context(state: CampaignState) -> dict:
    """Fetch browsing context for personalization."""
    profile = state["user_profile"]
    user_id = profile["user_id"]

    browsing_json = get_browsing_context.invoke({"user_id": user_id})
    browsing = json.loads(browsing_json)

    return {"browsing_context": browsing.get("browsing_activity", [])}


async def generate_email(state: CampaignState) -> dict:
    """Generate the campaign email using the LLM."""
    profile = state["user_profile"]
    top_5 = state.get("top_5_properties", [])
    browsing = state.get("browsing_context", [])

    # Build properties section
    properties_lines = []
    for i, prop in enumerate(top_5, 1):
        status = prop.get("listing_status", "active").upper()
        line = f"""
**Property {i}: {prop.get('address', 'N/A')}**
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
        properties_lines.append(line)

    properties_section = "\n".join(properties_lines) if properties_lines else "No properties available."

    # Build browsing section
    browsing_lines = []
    for b in browsing[:10]:
        browsing_lines.append(
            f"- [{b.get('activity_type', 'unknown')}] {b.get('address', 'N/A')} in {b.get('city', 'N/A')} "
            f"({b.get('property_type', 'N/A')}, ${int(float(b.get('price', 0))):,}) — {b.get('activity_timestamp', 'N/A')}"
        )
    browsing_section = "\n".join(browsing_lines) if browsing_lines else "No recent browsing activity."

    # Format the email generation prompt
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

    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    email_content = response.content

    # Build a user-facing summary message
    summary = f"""Campaign email generated for **{profile.get('first_name', '')} {profile.get('last_name', '')}** ({profile.get('email', '')}).

**Segment:** {profile.get('user_segment', '')}
**Target City:** {profile.get('preferred_city', '')}, {profile.get('preferred_state', '')}
**Properties Featured:** {len(top_5)} (from recommendation engine)
**Browsing Activities Referenced:** {len(browsing)}

---

{email_content}"""

    return {
        "campaign_email": email_content,
        "messages": [AIMessage(content=summary)],
    }


async def handle_error(state: CampaignState) -> dict:
    """Handle errors in the pipeline."""
    error = state.get("error", "An unknown error occurred.")
    return {"messages": [AIMessage(content=f"Campaign generation failed: {error}")]}


# --- Conditional Edges ---

def should_continue_after_input(state: CampaignState) -> str:
    if state.get("error"):
        return "handle_error"
    return "retrieve_candidates"


def should_continue_after_retrieval(state: CampaignState) -> str:
    candidates = state.get("candidate_properties", [])
    if not candidates or state.get("error"):
        return "handle_error"
    return "rank_and_select"


# --- Build the Graph ---

def build_campaign_graph() -> StateGraph:
    graph = StateGraph(CampaignState)

    # Add nodes
    graph.add_node("process_input", process_input)
    graph.add_node("retrieve_candidates", retrieve_candidates)
    graph.add_node("rank_and_select", rank_and_select)
    graph.add_node("enrich_context", enrich_context)
    graph.add_node("generate_email", generate_email)
    graph.add_node("handle_error", handle_error)

    # Add edges
    graph.add_edge(START, "process_input")
    graph.add_conditional_edges("process_input", should_continue_after_input)
    graph.add_conditional_edges("retrieve_candidates", should_continue_after_retrieval)
    graph.add_edge("rank_and_select", "enrich_context")
    graph.add_edge("enrich_context", "generate_email")
    graph.add_edge("generate_email", END)
    graph.add_edge("handle_error", END)

    return graph.compile()


# --- MCP Integration (optional Genie) ---

def init_mcp_client(workspace_client: WorkspaceClient) -> Optional[DatabricksMultiServerMCPClient]:
    """Initialize MCP client with Genie space if configured."""
    if GENIE_SPACE_ID.startswith("<"):
        logger.info("Genie space not configured, skipping MCP setup.")
        return None

    host_name = get_databricks_host_from_env()
    if not host_name:
        logger.warning("Could not determine Databricks host, skipping MCP setup.")
        return None

    return DatabricksMultiServerMCPClient(
        [
            DatabricksMCPServer(
                name="xome-genie",
                url=f"{host_name}/api/2.0/mcp/genie/{GENIE_SPACE_ID}",
                workspace_client=workspace_client,
            ),
        ]
    )


# --- MLflow Handlers ---

campaign_graph = build_campaign_graph()


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    outputs = [
        event.item
        async for event in stream_handler(request)
        if event.type == "response.output_item.done"
    ]
    return ResponsesAgentResponse(output=outputs)


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    if session_id := get_session_id(request):
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})

    messages = to_chat_completions_input([i.model_dump() for i in request.input])

    # Convert to LangChain message format
    lc_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        elif role == "system":
            lc_messages.append(SystemMessage(content=content))

    input_state = {"messages": lc_messages}

    async for event in process_agent_astream_events(
        campaign_graph.astream(input=input_state, stream_mode=["updates", "messages"])
    ):
        yield event
