# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Xome Campaign Platform — an AI-powered real estate campaign tool that generates personalized emails promoting recommended properties to high-intent buyers. Built with FastAPI backend, React + TailwindCSS frontend, LangGraph orchestration, deployed as a single-process Databricks App.

## Common Commands

```bash
# Local dev (runs backend on :8000 + frontend dev server on :3000 concurrently)
uv run start-app

# Build frontend for production
cd frontend && npm run build && cd ..

# Deploy (two-step: bundle then app)
databricks bundle deploy --target prod
databricks apps deploy xome-lakebase-campaign-genie --profile fevm --source-code-path /Workspace/Users/birbal.das@databricks.com/.bundle/xome_lakebase_campaign_genie/prod/files

# Run data pipeline (generate Delta tables)
databricks bundle run xome_setup_pipeline --target prod

# Run Lakebase migration (copy Delta → Lakebase)
databricks bundle run xome_migrate_to_lakebase --target prod

# Check app status / logs
databricks apps get xome-lakebase-campaign-genie --profile fevm
databricks apps logs xome-lakebase-campaign-genie --profile fevm
```

**Requirements:** Python 3.11+, `uv` for Python package management, Node.js/npm for frontend.

**No tests or linting** — There is no test suite, eslint, prettier, or ruff configured in this repo.

## Architecture

```
Browser → FastAPI (port 8000) → serves frontend/dist/ (static) + REST API (/api/campaign/*)
                                     │
                          ┌──────────┼──────────┐
                          ▼          ▼          ▼
                   LangGraph     Lakebase     Genie Spaces
                   StateGraph   (PostgreSQL)  (NL queries)
                      │
                      ▼
                  Claude LLM
```

**Single-process deployment:** FastAPI on port 8000 serves both the pre-built React frontend (from `frontend/dist/`) and all API endpoints. Databricks Apps only exposes port 8000.

**Dev mode:** `uv run start-app` launches backend (port 8000) and Vite dev server (port 3000) concurrently. Vite proxies `/api` requests to `localhost:8000` (configured in `vite.config.ts`).

**Two LangGraph paths (4 nodes total), routed by the `source` field in `CampaignState`:**

- **Dashboard** (`source=dashboard`): `route_entry → enrich_context → generate_email → END`. The frontend provides user profile and properties via the API request; `enrich_context` fetches browsing history from Lakebase; `generate_email` validates inputs, builds the prompt, and calls Claude.

- **Genie** (`source=genie`): `route_entry → query_genie → END`. Calls Genie Spaces API with natural language. Returns raw `columns` + `rows` directly to the frontend as a table.

## Key Paths

- Backend: `agent_server/`
- REST API router: `agent_server/campaign_api.py`
- Genie Spaces client: `agent_server/genie_client.py`
- LangGraph state: `agent_server/graph_state.py`
- LangGraph nodes: `agent_server/graph_nodes.py`
- LangGraph graph: `agent_server/graph.py`
- Email generation logic: `agent_server/email_generator.py`
- LLM setup: `agent_server/agent.py`
- Lakebase helper (psycopg2): `agent_server/tools.py`
- Config constants: `agent_server/config.py`
- Prompts: `agent_server/prompts.py`
- Server entry point: `agent_server/start_server.py`
- Frontend (React): `frontend/`
- Frontend components: `frontend/src/components/`
- Dashboard API client: `frontend/src/api/campaign.ts`
- Data generation: `notebooks/01_generate_data.py`
- Lakebase migration: `notebooks/02_migrate_to_lakebase.py`
- Deployment: `databricks.yml`, `databricks-genie.yml`, `app.yaml`

## Key Patterns

**`source` field routing** — The `source` field in `CampaignState` (`"dashboard"` or `"genie"`) routes the graph via `_route_source` in `graph.py`. Dashboard uses the email generation pipeline; Genie uses the user discovery pipeline.

**`CampaignState`** — TypedDict in `graph_state.py` with field groups:
- *Input:* `user_id`, `city`, `state`, `source`, `properties_input` (dashboard), `user_profile` (dashboard), `genie_query`, `genie_conversation_id` (genie)
- *Intermediate:* `browsing_context`
- *Genie output:* `genie_raw_result` (`{columns, rows, description, sql}`), `genie_conversation_id_out`, `genie_message_id`
- *Output:* `generated_email` (`{subject, html, plain_text, raw}`), `error`

**`_SanitizedChatDatabricks`** — Subclass in `agent.py` that strips `id` keys from tool message content blocks before sending to the Foundation Model API. Some LLM endpoints reject the extra `id` field that LangChain adds to content blocks.

**Email parsing** — `email_generator.py` uses regex (not JSON) to extract `SUBJECT:`, `HTML:`, and `PLAIN TEXT:` sections from raw LLM output. The prompt instructs the LLM to output in this delimited format.

**Connection pooling** — `tools.py` uses a thread-safe singleton psycopg2 connection (`_lock` + `_conn`) with auto-reconnect: on `OperationalError` (token expiry or connection drop), it refreshes the Databricks-issued Lakebase token and retries once.

**MLflow tracing** — `start_server.py` calls `mlflow.langchain.autolog()` on experiment `/Shared/xome-lakebase-campaign-tracing`. All LangGraph invocations are traced automatically.

**Startup table creation** — FastAPI lifespan hook in `start_server.py` auto-creates `campaign_tracking` and `campaign_emails` tables via `CREATE TABLE IF NOT EXISTS`.

**Frontend state management** — React hooks only (useState, useCallback, useEffect). No Redux/Zustand. `AppShell.tsx` is the main orchestrator holding Genie results, filter state, and view state.

**Genie raw table rendering** — The `/api/campaign/genie-query` endpoint returns raw `columns` and `rows` from Genie. The frontend `GenieResultTable` component renders these as a generic table. If a `user_id` column exists, those cells are clickable links that navigate to the user detail view. If a `property_id` column exists, those cells are clickable links that open a `PropertyDetailModal` with full property details and image.

**Genie search bar query retention** — After a Genie query completes, the submitted query text is displayed as placeholder text in the search input (replacing the default placeholder), so the user can see what they last searched for.

## Critical Rules

- Campaign email properties come ONLY from the `recommendations` table. Browsing data is for personalization context only.
- Frontend must be built (`cd frontend && npm run build`) before deploying — `frontend/dist/` is served as static files.
- `.gitignore` has `!frontend/dist/` exception to include the built frontend in bundle deploy.
- `.databricksignore` excludes `notebooks/`, `frontend/src/`, `node_modules/` etc. from the deploy bundle — only `frontend/dist/` and backend code are deployed.

## Data Model

Six tables in Lakebase (PostgreSQL). First four seeded by notebooks, last two auto-created at startup:

- `users` (500 rows) — buyer profiles with preferences (city, state, budget, property type, segment)
- `properties` (1,000 rows) — listings with details (price, beds, baths, sqft, neighborhood, school rating, auction info)
- `browsing_activity` (10,000 rows) — user browsing events linked to properties
- `recommendations` (5,000 rows) — ML-scored property recommendations per user (`recommendation_score` 0.0–1.0)
- `campaign_tracking` — records which emails were sent for which user+property+recommendation
- `campaign_emails` — saved email content (subject, html_body, plain_text, filename)

## REST API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/campaign/filters` | Distinct cities, states, types, segments, price ranges |
| `POST` | `/api/campaign/genie-query` | Natural language query → raw columns + rows from Genie Spaces |
| `GET` | `/api/campaign/properties/{id}` | Full property details by ID |
| `GET` | `/api/campaign/users/{id}/profile` | Full user profile |
| `POST` | `/api/campaign/users/{id}/listings` | Top recommended properties for a user |
| `POST` | `/api/campaign/generate-email` | Generate email via LangGraph (source=dashboard) |
| `POST` | `/api/campaign/save-email` | Save email to Lakebase |

## Configuration

- Workspace: fevm (`https://fevm-serverless-stable-14ey07.cloud.databricks.com`)
- App URL: `https://xome-lakebase-campaign-genie-7474645414452466.aws.databricksapps.com`
- Genie Space ID: `01f1484fd22e1d558c5ed706de7b522d`
- All other config values (catalog, schema, Lakebase DNS, LLM endpoint, etc.) are in `agent_server/config.py`.
