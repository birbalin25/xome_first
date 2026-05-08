"""Genie Spaces API wrapper for natural language user discovery."""

import asyncio
import json
import logging
import time
import urllib.request
from datetime import timedelta

from databricks.sdk import WorkspaceClient

from agent_server.config import GENIE_SPACE_ID

logger = logging.getLogger(__name__)

_ws = WorkspaceClient()

# In-process rate limiting: Genie allows ~5 queries/min
_last_post_time: float = 0.0
_rate_limit_interval: float = 12.0  # seconds between POST calls


def _wait_for_rate_limit():
    """Block until enough time has passed since the last POST call."""
    global _last_post_time
    now = time.monotonic()
    elapsed = now - _last_post_time
    if _last_post_time > 0 and elapsed < _rate_limit_interval:
        wait = _rate_limit_interval - elapsed
        logger.debug("Rate limiting: waiting %.1fs before next Genie call", wait)
        time.sleep(wait)
    _last_post_time = time.monotonic()


def _run_query(query: str, conversation_id: str | None, space_id: str) -> dict:
    """Run a Genie query using the SDK's built-in wait mechanism, then extract results."""
    _wait_for_rate_limit()

    # Start or continue conversation — SDK returns a Wait object with built-in polling
    if conversation_id:
        wait_obj = _ws.genie.create_message(
            space_id=space_id,
            conversation_id=conversation_id,
            content=query,
        )
    else:
        wait_obj = _ws.genie.start_conversation(
            space_id=space_id,
            content=query,
        )

    # Wait for completion (SDK polls internally)
    # The SDK raises an exception if status is FAILED, so we catch it
    # and fetch the message again to extract error details.
    conv_id = wait_obj.conversation_id
    msg_id = wait_obj.message_id

    try:
        msg = wait_obj.result(timeout=timedelta(seconds=120))
    except Exception as wait_err:
        # On failure, fetch the message to get error details
        try:
            msg = _ws.genie.get_message(
                space_id=space_id,
                conversation_id=conv_id,
                message_id=msg_id,
            )
        except Exception:
            raise RuntimeError(f"Genie query failed: {wait_err}") from wait_err

        error_msg = f"Genie query FAILED"
        if msg.error:
            error_type = msg.error.type.value if msg.error.type else "UNKNOWN"
            error_text = msg.error.error or ""
            error_msg = f"Genie query FAILED ({error_type}): {error_text}"
        elif msg.attachments:
            for att in msg.attachments:
                if att.text and att.text.content:
                    error_msg = f"Genie query FAILED: {att.text.content}"
                    break
        logger.error("Genie error: %s", error_msg)
        raise RuntimeError(error_msg)

    # Extract result
    result = {
        "conversation_id": conv_id,
        "message_id": msg_id,
        "columns": [],
        "rows": [],
        "description": "",
        "sql": "",
    }

    if not msg.attachments:
        logger.debug("Genie completed but no attachments")
        return result

    # Extract text description and SQL, find query attachment
    query_attachment_id = None
    for att in msg.attachments:
        if att.text and att.text.content:
            result["description"] = att.text.content
        if att.query:
            if att.query.query:
                result["sql"] = att.query.query
            # Get the attachment_id for fetching results
            query_attachment_id = att.attachment_id or getattr(att.query, "id", None)

    logger.debug("Genie SQL: %s", result["sql"])
    logger.debug("Genie query_attachment_id: %s", query_attachment_id)

    # Fetch tabular results
    try:
        if query_attachment_id:
            query_result = _ws.genie.get_message_attachment_query_result(
                space_id=space_id,
                conversation_id=conv_id,
                message_id=msg_id,
                attachment_id=query_attachment_id,
            )
        else:
            query_result = _ws.genie.get_message_query_result(
                space_id=space_id,
                conversation_id=conv_id,
                message_id=msg_id,
            )

        stmt = query_result.statement_response
        if stmt:
            logger.debug(
                "Statement status=%s, manifest=%s, result=%s",
                stmt.status.state.value if stmt.status and stmt.status.state else "N/A",
                stmt.manifest is not None,
                stmt.result is not None,
            )

            # Extract columns
            if stmt.manifest and stmt.manifest.schema and stmt.manifest.schema.columns:
                result["columns"] = [
                    {
                        "name": col.name or f"col_{col.position}",
                        "type": col.type_name.value if col.type_name else "STRING",
                    }
                    for col in stmt.manifest.schema.columns
                ]

            # Extract rows from inline data_array
            if stmt.result and stmt.result.data_array:
                result["rows"] = stmt.result.data_array
                logger.debug("Got %d inline rows", len(result["rows"]))

            # If no inline data, try external_links
            elif stmt.result and stmt.result.external_links:
                logger.debug("Result uses external_links, fetching...")
                all_rows = []
                for link in stmt.result.external_links:
                    if link.external_link:
                        req = urllib.request.Request(link.external_link)
                        for k, v in (link.http_headers or {}).items():
                            req.add_header(k, v)
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            data = resp.read().decode("utf-8")
                        for line in data.strip().split("\n"):
                            if line.strip():
                                all_rows.append(json.loads(line))
                result["rows"] = all_rows
                logger.debug("Got %d rows from external_links", len(result["rows"]))
            else:
                logger.debug(
                    "No data: total_row_count=%s",
                    stmt.manifest.total_row_count if stmt.manifest else "N/A",
                )
        else:
            logger.debug("No statement_response in query result")
    except Exception:
        logger.exception("Failed to extract Genie query result")

    return result


async def query_genie(
    query: str,
    conversation_id: str | None = None,
    space_id: str = GENIE_SPACE_ID,
) -> dict:
    """Query Genie Spaces API, returning columns + rows.

    Args:
        query: Natural language query string.
        conversation_id: If provided, sends a follow-up in existing conversation.
        space_id: Genie Space ID to query.

    Returns:
        dict with keys: conversation_id, message_id, columns, rows, description, sql
    """
    return await asyncio.to_thread(_run_query, query, conversation_id, space_id)
