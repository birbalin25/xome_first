# Xome Campaign Platform — Workflow

## Architecture Diagram

```mermaid
flowchart TD
    classDef ui fill:#4ade80,stroke:#16a34a,stroke-width:2px,color:#000
    classDef api fill:#60a5fa,stroke:#2563eb,stroke-width:2px,color:#000
    classDef gn fill:#f9a8d4,stroke:#ec4899,stroke-width:2px,color:#000
    classDef er fill:#fca5a5,stroke:#ef4444,stroke-width:2px,color:#000
    classDef llm fill:#c084fc,stroke:#9333ea,stroke-width:2px,color:#000
    classDef db fill:#7dd3fc,stroke:#0ea5e9,stroke-width:2px,color:#000
    classDef lb fill:#86efac,stroke:#22c55e,stroke-width:2px,color:#000
    classDef pt fill:#e9d5ff,stroke:#a855f7,stroke-width:3px,color:#000
    classDef legend fill:#fff,stroke:#94a3b8,stroke-width:1px,color:#000

    %% ── Legend ──
    subgraph LEG["Legend"]
        direction LR
        L1["A"]:::legend -->|"Solid line = graph flow / always executes"| L2["B"]:::legend
        L3["C"]:::legend -.->|"Dashed line = conditional / data read"| L4["D"]:::legend
    end

    %% ── Frontend ──
    subgraph FE["Frontend — React + TailwindCSS"]
        direction LR
        D["Dashboard View<br/>Filters → Users → Select Properties<br/>→ Generate Email"]:::ui
        C["Chat View<br/>Natural language input"]:::ui
    end

    %% ── REST API ──
    subgraph API["FastAPI — Port 8000"]
        direction LR
        subgraph SQL_EP["Direct SQL Endpoints"]
            A1["GET /filters"]:::api
            A2["POST /users"]:::api
            A3["GET /users/:id/profile"]:::api
            A4["POST /users/:id/listings"]:::api
            A5["POST /save-email"]:::api
        end
        subgraph LG_EP["LangGraph Endpoints"]
            G1["POST /generate-email"]:::api
            G2["POST /chat/message"]:::api
            G3["POST /invocations"]:::api
        end
    end

    %% ── LangGraph + Data + LLM (single layer) ──
    subgraph CORE["LangGraph Pipeline + Data + LLM"]
        direction LR

        subgraph LG["StateGraph — 6 Nodes"]
            direction TB
            S(["START"]):::pt
            P1["1. process_input<br/>Dashboard: reuses profile from frontend<br/>Chat: fetches from users table"]:::gn
            P2["2. retrieve_candidates<br/>Dashboard: reuses properties from frontend<br/>Chat: queries recommendations table"]:::gn
            P3["3. rank_and_select<br/>Dashboard: pass-through, no processing<br/>Chat: sort by score, pick top N"]:::gn
            P4["4. enrich_context<br/>Always runs: fetches browsing history<br/>from Lakebase"]:::gn
            P5["5. generate_email<br/>Prompt → Claude → parse"]:::gn
            ERR["6. handle_error<br/>Format error response"]:::er
            EN(["END"]):::pt

            S --> P1
            P1 -->|ok| P2
            P1 -.->|error| ERR
            P2 --> P3
            P3 -->|ok| P4
            P3 -.->|error| ERR
            P4 --> P5
            P5 --> EN
            ERR --> EN
        end

        LLM["Claude Sonnet 4.6<br/>Foundation Model API"]:::llm

        subgraph LB_DB["Lakebase — Managed PostgreSQL"]
            direction TB
            T1["users · 500"]:::lb
            T2["properties · 1K"]:::lb
            T3["recommendations · 5K"]:::lb
            T4["browsing · 10K"]:::lb
            T5["campaign_tracking"]:::lb
        end

        VOL["UC Volume:<br/>campaign_emails"]:::db
    end

    %% ── Output ──
    subgraph OUT["Output"]
        direction LR
        O1["Dashboard<br/>Email Preview + Save"]:::ui
        O2["Chat<br/>Reply + Inline Email"]:::ui
    end

    %% ── Vertical flow ──
    D -->|"user_id + profile + properties"| G1
    D -.->|"filters, users, listings"| SQL_EP
    C -->|"raw_message"| G2
    G1 & G2 & G3 --> S
    P5 --> LLM
    SQL_EP --> LB_DB
    EN -->|dashboard| O1
    EN -->|chat| O2
    O1 -->|save file| VOL
    O1 -->|"track sent"| T5

    %% ── Data reads ──
    P1 -.->|"chat path only"| T1
    P2 -.->|"chat path only"| T3
    P4 -.->|"always: browsing context"| T4
    A4 -.->|"LEFT JOIN"| T5
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React + TailwindCSS + Vite | Dashboard & Chat UI |
| Backend | FastAPI (Python) | REST API, static file serving |
| Orchestration | LangGraph StateGraph | 6-node agentic pipeline |
| LLM | Claude Sonnet 4.6 (Foundation Model API) | Email content generation |
| Database | Lakebase (Managed PostgreSQL) | OLTP queries, user/property data |
| Storage | Unity Catalog Volume | Persisted email HTML files |
| Tracing | MLflow Autolog | LangGraph node I/O tracing |
| Deployment | Databricks Apps | Single-process, port 8000 |

## Data Model (Lakebase)

| Table | Rows | Primary Key | Description |
|-------|------|-------------|-------------|
| users | 500 | user_id | Buyer profiles: name, email, preferences, budget, segment |
| properties | 1,000 | property_id | Listings: address, price, beds/baths, sqft, school rating |
| recommendations | 5,000 | recommendation_id | ML-scored user-property matches with reasons |
| browsing_activity | 10,000 | activity_id | Clickstream: views, searches, favorites, sessions |
| campaign_tracking | varies | (none) | Tracks which emails have been sent per user-property pair |

## REST API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/campaign/filters | Distinct cities, states, types, segments, price ranges |
| POST | /api/campaign/users | Top 20 users matching filter criteria |
| GET | /api/campaign/users/{id}/profile | Full buyer profile |
| POST | /api/campaign/users/{id}/listings | Top 5 recommended properties with campaign status |
| POST | /api/campaign/generate-email | Generate email via LangGraph (source=dashboard) |
| POST | /api/campaign/save-email | Save email HTML to UC Volume + track in campaign_tracking |
| POST | /api/chat/message | Chat interface — natural language to LangGraph (source=chat) |
| POST | /invocations | MLflow-compatible endpoint for model serving |

## LangGraph Pipeline — Node Details

### Node 1: process_input
- **Dashboard path:** Frontend already loaded the user profile. Pass-through, zero DB queries.
- **Chat path:** Extracts user_id from natural language, queries the `users` table.

### Node 2: retrieve_candidates
- **Dashboard path:** Frontend already selected properties. Pass-through.
- **Chat path:** Queries `recommendations` joined with `properties` for ML-scored matches.

### Node 3: rank_and_select
- **Dashboard path:** Pass-through — user already chose properties in the UI.
- **Chat path:** Sorts by recommendation_score descending, picks top N.

### Node 4: enrich_context
- **Both paths:** Always queries `browsing_activity` joined with `properties` for recent user behavior (views, searches, favorites, session durations).

### Node 5: generate_email
- Assembles prompt with buyer profile, selected properties, and browsing context.
- Calls Claude Sonnet 4.6 via Foundation Model API.
- Parses response into subject line and HTML body.

### Node 6: handle_error
- Catches errors from nodes 1 and 3, formats user-friendly error response.

## Data Flow

### Dashboard Path (Optimized)

```
User selects filters → Frontend calls /filters, /users, /profile, /listings
  → User clicks "Generate Email" with selected properties
  → POST /generate-email sends user profile + properties to LangGraph
  → Nodes 1-3: pass-through (data already provided by frontend)
  → Node 4: queries browsing_activity from Lakebase
  → Node 5: Claude generates personalized email
  → Email displayed for review
  → User clicks "Save" → HTML saved to UC Volume + campaign_tracking updated
```

### Chat Path (Autonomous)

```
User types natural-language request
  → POST /chat/message sends raw_message to LangGraph
  → Node 1: queries users table from Lakebase
  → Node 2: queries recommendations + properties from Lakebase
  → Node 3: ranks and selects top properties
  → Node 4: queries browsing_activity from Lakebase
  → Node 5: Claude generates personalized email
  → Email returned inline in chat response
```
